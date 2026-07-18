import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_audit_event
from app.errors import ConflictError, NotFoundError, ValidationErrorApp
from app.knowledge import repository
from app.knowledge.models import KnowledgeSource, KnowledgeSourceVersion
from app.knowledge.schemas import SourceGovernanceUpdateRequest, SourceRegisterRequest

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
