import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_audit_event
from app.errors import ConflictError, NotFoundError, ValidationErrorApp
from app.knowledge import repository, storage, validation
from app.knowledge.embeddings import EmbeddingProvider
from app.knowledge.extraction.registry import extract
from app.knowledge.indexing import index_source_version
from app.knowledge.models import KnowledgeIngestionJob, KnowledgeSource, KnowledgeSourceVersion
from app.knowledge.schemas import SourceGovernanceUpdateRequest, SourceRegisterRequest
from app.logging import get_logger
from app.notifications.service import notify

logger = get_logger(__name__)

# Visibilities that are never eligible for retrieval regardless of other
# governance state — archive/template sources are history/packaging
# artifacts, never live content (RKPR_RAG_FINAL_DOCS §"never active" rule,
# WEBSITE_RAG_SYNC_POLICY.md rule 8).
_NEVER_RETRIEVABLE_VISIBILITY = {"archive", "template"}


async def register_source(
    db: AsyncSession, *, body: SourceRegisterRequest, actor_user_id: uuid.UUID | None
) -> KnowledgeSource:
    if body.source_id:
        existing = await repository.get_source_by_external_id(db, body.source_id)
        if existing is not None:
            raise ConflictError(f"A source with source_id '{body.source_id}' already exists")

    source = KnowledgeSource(
        source_id=body.source_id,
        title=body.title,
        description=body.description,
        source_type=body.source_type,
        category=body.category,
        subcategory=body.subcategory,
        language=body.language,
        visibility=body.visibility,
        source_priority=body.source_priority,
        authoritative=body.authoritative,
        ocr_required=body.ocr_required,
        effective_date=body.effective_date,
        expiry_date=body.expiry_date,
        source_url=body.source_url,
        tags=body.tags,
        source_metadata=body.source_metadata,
        created_by=actor_user_id,
    )
    db.add(source)
    await db.flush()

    await record_audit_event(
        db,
        actor_user_id=actor_user_id,
        action="knowledge_source.registered",
        resource_type="knowledge_source",
        resource_id=str(source.id),
        after_state={"title": body.title, "source_type": body.source_type, "visibility": body.visibility},
        metadata={"source_id": body.source_id},
    )
    await db.commit()
    await db.refresh(source)
    return source


async def get_source_or_404(db: AsyncSession, source_id: uuid.UUID) -> KnowledgeSource:
    source = await repository.get_source(db, source_id)
    if source is None:
        raise NotFoundError("Knowledge source not found")
    return source


async def update_source_governance(
    db: AsyncSession,
    *,
    source_id: uuid.UUID,
    body: SourceGovernanceUpdateRequest,
    actor_user_id: uuid.UUID | None,
) -> KnowledgeSource:
    source = await get_source_or_404(db, source_id)

    updates = body.model_dump(exclude_unset=True)
    before_state = {field: getattr(source, field) for field in updates}
    for field, value in updates.items():
        setattr(source, field, value)

    # A visibility change into archive/template must also revoke
    # retrieval_enabled immediately — the DB-level gate a guest query
    # relies on can never lag behind a governance edit.
    if source.visibility in _NEVER_RETRIEVABLE_VISIBILITY:
        source.retrieval_enabled = False

    await repository.sync_chunk_governance(db, source)

    await record_audit_event(
        db,
        actor_user_id=actor_user_id,
        action="knowledge_source.governance_updated",
        resource_type="knowledge_source",
        resource_id=str(source.id),
        before_state=before_state,
        after_state=updates,
        metadata={"fields": list(updates.keys())},
    )
    await db.commit()
    await db.refresh(source)
    return source


async def approve_source(db: AsyncSession, *, source_id: uuid.UUID, actor_user_id: uuid.UUID | None) -> KnowledgeSource:
    source = await get_source_or_404(db, source_id)
    source.approval_status = "approved"
    source.approved_by = actor_user_id
    source.approved_at = datetime.now(UTC)

    await record_audit_event(
        db,
        actor_user_id=actor_user_id,
        action="knowledge_source.approved",
        resource_type="knowledge_source",
        resource_id=str(source.id),
        metadata={},
    )
    await db.commit()
    await db.refresh(source)
    return source


async def reject_source(
    db: AsyncSession, *, source_id: uuid.UUID, reason: str, actor_user_id: uuid.UUID | None
) -> KnowledgeSource:
    source = await get_source_or_404(db, source_id)
    source.approval_status = "rejected"
    source.status = "rejected"
    source.retrieval_enabled = False
    await repository.sync_chunk_governance(db, source)

    await record_audit_event(
        db,
        actor_user_id=actor_user_id,
        action="knowledge_source.rejected",
        resource_type="knowledge_source",
        resource_id=str(source.id),
        metadata={"reason": reason},
    )
    await db.commit()
    await db.refresh(source)
    return source


async def activate_source(
    db: AsyncSession, *, source_id: uuid.UUID, actor_user_id: uuid.UUID | None
) -> KnowledgeSource:
    """The only path by which retrieval_enabled ever becomes true. Enforces
    every precondition explicitly rather than trusting the caller — this is
    the concrete implementation of the brief's "never rely solely on LLM
    prompt instructions" rule at the governance layer: a source cannot
    reach guests without having passed approval, malware scanning, and
    processing, no matter what any other code path requests."""
    source = await get_source_or_404(db, source_id)

    problems = []
    if source.approval_status != "approved":
        problems.append("source is not approved")
    if source.processing_status != "completed":
        problems.append(f"processing_status is '{source.processing_status}', not 'completed'")
    if source.malware_scan_status not in ("clean", "unscanned_dev_only"):
        problems.append(f"malware_scan_status is '{source.malware_scan_status}'")
    if source.visibility in _NEVER_RETRIEVABLE_VISIBILITY:
        problems.append(f"visibility '{source.visibility}' is never retrieval-eligible")
    if problems:
        raise ValidationErrorApp(f"Cannot activate source: {'; '.join(problems)}")

    source.status = "active"
    source.retrieval_enabled = True
    await repository.sync_chunk_governance(db, source)

    await record_audit_event(
        db,
        actor_user_id=actor_user_id,
        action="knowledge_source.activated",
        resource_type="knowledge_source",
        resource_id=str(source.id),
        metadata={},
    )
    await db.commit()
    await db.refresh(source)
    return source


async def archive_source(db: AsyncSession, *, source_id: uuid.UUID, actor_user_id: uuid.UUID | None) -> KnowledgeSource:
    source = await get_source_or_404(db, source_id)
    source.status = "archived"
    source.retrieval_enabled = False
    await repository.sync_chunk_governance(db, source)

    await record_audit_event(
        db,
        actor_user_id=actor_user_id,
        action="knowledge_source.archived",
        resource_type="knowledge_source",
        resource_id=str(source.id),
        metadata={},
    )
    await db.commit()
    await db.refresh(source)
    return source


async def reprocess_source(
    db: AsyncSession, *, source_id: uuid.UUID, actor_user_id: uuid.UUID | None, embedding_provider: EmbeddingProvider
) -> KnowledgeSource:
    """Re-runs extraction -> chunking -> embedding against the file already
    stored for this source's current version — the same recovery path used
    manually to fix a stuck/mis-chunked source (e.g. the restaurant menu
    incident), now exposed as a real dashboard action instead of a one-off
    script. Website sources aren't covered here; a website source has no
    single stored file to re-extract — re-ingesting it means triggering a
    fresh crawl (POST /website/crawl), a distinct, already-existing flow."""
    source = await get_source_or_404(db, source_id)
    if source.source_type != "document":
        raise ValidationErrorApp("Only document sources can be reprocessed; website sources use a fresh crawl")
    if not source.storage_path or source.current_version_id is None:
        raise ValidationErrorApp("Source has no stored file to reprocess")

    version = await repository.get_version(db, source.current_version_id)
    if version is None:
        raise ValidationErrorApp("Source has no current version to reprocess")

    job = KnowledgeIngestionJob(
        job_type="reprocess",
        job_status="running",
        source_id=source.id,
        started_at=datetime.now(UTC),
        created_by=actor_user_id,
    )
    db.add(job)

    source.processing_status = "extracting"
    version.processing_status = "extracting"
    version.error_message = None
    await db.commit()

    try:
        content = await storage.download_file(source.storage_path)
        validation_result = validation.validate_upload(source.original_filename or "reprocessed", content)
        extracted = extract(validation_result.file_format, content)
        result = await index_source_version(
            db, source=source, version=version, extracted=extracted, provider=embedding_provider
        )
    except Exception as exc:
        version.processing_status = "failed"
        version.error_message = str(exc)[:4000]
        source.processing_status = "failed"
        job.job_status = "failed"
        job.completed_at = datetime.now(UTC)
        job.error_message = str(exc)[:4000]
        await record_audit_event(
            db,
            actor_user_id=actor_user_id,
            action="knowledge_source.reprocess_failed",
            resource_type="knowledge_source",
            resource_id=str(source.id),
            metadata={"error": str(exc)[:500]},
        )
        await db.commit()
        await notify(
            db,
            notification_type="knowledge_ingestion_failed",
            title=f"Reprocessing failed: {source.title}",
            body=str(exc)[:500],
            resource_type="knowledge_source",
            resource_id=str(source.id),
        )
        raise

    version.processing_status = "completed" if not extracted.pages_needing_ocr else "needs_review"
    source.processing_status = version.processing_status
    job.job_status = "completed"
    job.completed_at = datetime.now(UTC)
    job.progress_current = 1
    job.progress_total = 1
    job.result_summary = {
        "chunks_created": result.chunks_created,
        "chunks_updated": result.chunks_updated,
        "chunks_deleted": result.chunks_deleted,
        "chunks_embedded": result.chunks_embedded,
    }

    await record_audit_event(
        db,
        actor_user_id=actor_user_id,
        action="knowledge_source.reprocessed",
        resource_type="knowledge_source",
        resource_id=str(source.id),
        metadata=job.result_summary,
    )
    await db.commit()
    await db.refresh(source)
    return source


async def delete_source(db: AsyncSession, *, source_id: uuid.UUID, actor_user_id: uuid.UUID | None) -> None:
    """Hard delete — cascades to versions/chunks/crawl-runs via the FK
    ondelete=CASCADE already declared on those tables (see models.py).
    Guarded against removing anything still live: a source must be
    archived or rejected first, so this can never be used to silently
    yank guest-visible content out from under an in-flight conversation."""
    source = await get_source_or_404(db, source_id)
    if source.status == "active" or source.retrieval_enabled:
        raise ConflictError("Cannot delete an active, retrieval-enabled source — archive it first")

    await record_audit_event(
        db,
        actor_user_id=actor_user_id,
        action="knowledge_source.deleted",
        resource_type="knowledge_source",
        resource_id=str(source.id),
        before_state={"title": source.title, "status": source.status, "visibility": source.visibility},
        metadata={"source_id": source.source_id},
    )
    if source.storage_path:
        try:
            await storage.delete_file(source.storage_path)
        except Exception:
            logger.warning("knowledge_source_delete_file_failed", extra={"storage_path": source.storage_path})

    await db.delete(source)
    await db.commit()


async def record_source_version(
    db: AsyncSession,
    *,
    source_id: uuid.UUID,
    checksum_sha256: str,
    storage_path: str | None,
    actor_user_id: uuid.UUID | None,
) -> KnowledgeSourceVersion:
    """Creates the next version row for a source and points current_version_id
    at it. Idempotent re-ingestion (skip entirely when checksum is
    unchanged from the current version) is the caller's responsibility —
    app.knowledge.scripts.import_rkpr_knowledge and the upload endpoint
    both check before calling this, so this function always creates a real
    new version when invoked."""
    source = await get_source_or_404(db, source_id)

    next_number = await repository.get_latest_version_number(db, source_id) + 1
    await repository.clear_current_version_flag(db, source_id)

    version = KnowledgeSourceVersion(
        source_id=source_id,
        version_number=next_number,
        storage_path=storage_path,
        checksum_sha256=checksum_sha256,
        is_current=True,
    )
    db.add(version)
    await db.flush()

    source.current_version_id = version.id
    source.checksum_sha256 = checksum_sha256
    if storage_path:
        source.storage_path = storage_path
    source.processing_status = "pending"

    await record_audit_event(
        db,
        actor_user_id=actor_user_id,
        action="knowledge_source.version_recorded",
        resource_type="knowledge_source",
        resource_id=str(source.id),
        metadata={"version_number": next_number},
    )
    await db.commit()
    await db.refresh(version)
    return version
