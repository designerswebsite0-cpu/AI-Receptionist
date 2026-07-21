import hashlib
import uuid

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import PageParams
from app.common.responses import success
from app.database import get_db
from app.deps import get_current_user
from app.errors import ConflictError, NotFoundError, ValidationErrorApp
from app.knowledge import malware, repository, service, storage, validation
from app.knowledge.embeddings import EmbeddingProvider, get_embedding_provider
from app.knowledge.extraction.registry import extract
from app.knowledge.indexing import index_source_version
from app.knowledge.retrieval import service as retrieval_service
from app.knowledge.retrieval.reranker import HeuristicReranker
from app.knowledge.schemas import (
    ChunkListResponse,
    ChunkOut,
    CrawlRunOut,
    IngestionJobOut,
    JobListResponse,
    MediaOut,
    SearchRequest,
    SearchResponse,
    SourceGovernanceUpdateRequest,
    SourceListResponse,
    SourceOut,
    SourceRegisterRequest,
    SourceRejectRequest,
    SourceVersionOut,
    WebsiteCrawlRequest,
)
from app.knowledge.website.seed import WebsiteCrawlSeed
from app.knowledge.website.service import run_crawl
from app.users.models import User

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


# --- sources ------------------------------------------------------------------


@router.post("/sources/upload")
async def upload_source(
    file: UploadFile = File(...),
    title: str = Form(...),
    visibility: str = Form(...),
    source_id: str | None = Form(default=None),
    category: str | None = Form(default=None),
    source_priority: str = Form(default="normal"),
    authoritative: bool = Form(default=False),
    ocr_required: bool = Form(default=False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> dict:
    content = await file.read()
    validation_result = validation.validate_upload(file.filename or "upload", content)
    checksum = hashlib.sha256(content).hexdigest()

    existing = await repository.get_source_by_checksum(db, checksum)
    if existing is not None:
        raise ConflictError(f"An identical file already exists as source {existing.id}")

    # Fail-closed malware scan (app/knowledge/malware.py) — was previously
    # built but never called anywhere, leaving every upload's
    # malware_scan_status stuck at its 'pending' default forever, which
    # permanently blocked activate_source's governance check. An INFECTED
    # result is rejected outright, before anything is stored; every other
    # result is recorded honestly (never silently treated as 'clean').
    scan_result = await malware.ClamAVScanner().scan(content)
    if scan_result.status == malware.ScanStatus.INFECTED:
        raise ValidationErrorApp(f"File failed malware scan: {scan_result.detail or 'infected'}")
    resolved_scan_status = malware.resolve_scan_status(scan_result)

    body = SourceRegisterRequest(
        source_id=source_id,
        title=title,
        source_type="document",
        category=category,
        visibility=visibility,
        source_priority=source_priority,
        authoritative=authoritative,
        ocr_required=ocr_required,
    )
    source = await service.register_source(db, body=body, actor_user_id=user.id)
    source.malware_scan_status = resolved_scan_status

    storage_path = f"sources/{source.id}/{validation_result.sanitized_filename}"
    await storage.upload_file(storage_path, content)
    version = await service.record_source_version(
        db, source_id=source.id, checksum_sha256=checksum, storage_path=storage_path, actor_user_id=user.id
    )

    extracted = extract(validation_result.file_format, content)
    await index_source_version(db, source=source, version=version, extracted=extracted, provider=embedding_provider)
    version.processing_status = "completed" if not extracted.pages_needing_ocr else "needs_review"
    source.processing_status = version.processing_status
    await db.commit()
    await db.refresh(source)

    return success(SourceOut.model_validate(source).model_dump(mode="json"))


@router.get("/sources")
async def list_sources(
    source_type: str | None = Query(default=None),
    visibility: str | None = Query(default=None),
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    params = PageParams(page=page, page_size=page_size)
    sources, total = await repository.list_sources(
        db,
        source_type=source_type,
        visibility=visibility,
        status=status,
        search=search,
        offset=params.offset,
        limit=params.page_size,
    )
    response = SourceListResponse(
        items=[SourceOut.model_validate(s) for s in sources], total=total, offset=params.offset, limit=params.page_size
    )
    return success(response.model_dump(mode="json"))


@router.get("/sources/{source_id}")
async def get_source(
    source_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    source = await service.get_source_or_404(db, source_id)
    return success(SourceOut.model_validate(source).model_dump(mode="json"))


@router.patch("/sources/{source_id}")
async def update_source_governance(
    source_id: uuid.UUID,
    body: SourceGovernanceUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    source = await service.update_source_governance(db, source_id=source_id, body=body, actor_user_id=user.id)
    return success(SourceOut.model_validate(source).model_dump(mode="json"))


@router.post("/sources/{source_id}/approve")
async def approve_source(
    source_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    source = await service.approve_source(db, source_id=source_id, actor_user_id=user.id)
    return success(SourceOut.model_validate(source).model_dump(mode="json"))


@router.post("/sources/{source_id}/reject")
async def reject_source(
    source_id: uuid.UUID,
    body: SourceRejectRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    source = await service.reject_source(db, source_id=source_id, reason=body.reason, actor_user_id=user.id)
    return success(SourceOut.model_validate(source).model_dump(mode="json"))


@router.post("/sources/{source_id}/activate")
async def activate_source(
    source_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    source = await service.activate_source(db, source_id=source_id, actor_user_id=user.id)
    return success(SourceOut.model_validate(source).model_dump(mode="json"))


@router.post("/sources/{source_id}/archive")
async def archive_source(
    source_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    source = await service.archive_source(db, source_id=source_id, actor_user_id=user.id)
    return success(SourceOut.model_validate(source).model_dump(mode="json"))


@router.get("/sources/{source_id}/versions")
async def list_source_versions(
    source_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    await service.get_source_or_404(db, source_id)
    versions = await repository.list_versions(db, source_id)
    return success([SourceVersionOut.model_validate(v).model_dump(mode="json") for v in versions])


@router.post("/sources/{source_id}/reprocess")
async def reprocess_source(
    source_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> dict:
    source = await service.reprocess_source(
        db, source_id=source_id, actor_user_id=user.id, embedding_provider=embedding_provider
    )
    return success(SourceOut.model_validate(source).model_dump(mode="json"))


@router.delete("/sources/{source_id}")
async def delete_source(
    source_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    await service.delete_source(db, source_id=source_id, actor_user_id=user.id)
    return success({"deleted": True})


@router.get("/sources/{source_id}/chunks")
async def list_source_chunks(
    source_id: uuid.UUID,
    chunk_type: str | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await service.get_source_or_404(db, source_id)
    params = PageParams(page=page, page_size=page_size)
    chunks, total = await repository.list_chunks_paginated(
        db,
        source_id=source_id,
        chunk_type=chunk_type,
        search=search,
        offset=params.offset,
        limit=params.page_size,
    )
    response = ChunkListResponse(
        items=[ChunkOut.model_validate(c) for c in chunks], total=total, offset=params.offset, limit=params.page_size
    )
    return success(response.model_dump(mode="json"))


# --- media ----------------------------------------------------------------


@router.get("/media")
async def list_media(
    source_id: uuid.UUID = Query(...), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    media = await repository.list_media(db, source_id)
    return success([MediaOut.model_validate(m).model_dump(mode="json") for m in media])


# --- ingestion jobs -------------------------------------------------------------


@router.get("/jobs")
async def list_jobs(
    job_type: str | None = Query(default=None),
    job_status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    params = PageParams(page=page, page_size=page_size)
    jobs, total = await repository.list_jobs(
        db, job_type=job_type, job_status=job_status, offset=params.offset, limit=params.page_size
    )
    response = JobListResponse(
        items=[IngestionJobOut.model_validate(j) for j in jobs],
        total=total,
        offset=params.offset,
        limit=params.page_size,
    )
    return success(response.model_dump(mode="json"))


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    job = await repository.get_job(db, job_id)
    if job is None:
        raise NotFoundError("Ingestion job not found")
    return success(IngestionJobOut.model_validate(job).model_dump(mode="json"))


# --- retrieval (staff search playground) --------------------------------------


@router.post("/search")
async def search_knowledge(
    body: SearchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> dict:
    response: SearchResponse = await retrieval_service.search(
        db,
        query_text=body.query,
        embedding_provider=embedding_provider,
        reranker=HeuristicReranker(),
        guest_only=body.guest_only,
        limit=body.limit,
        chunk_type=body.chunk_type,
        conversation_id=body.conversation_id,
        requested_channel=body.requested_channel or "dashboard_playground",
        requested_by=user.id,
    )
    return success(response.model_dump(mode="json"))


# --- website crawling ----------------------------------------------------------


@router.post("/website/crawl")
async def trigger_website_crawl(
    body: WebsiteCrawlRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> dict:
    source = await repository.get_source_by_external_id(db, body.source_id)
    if source is None:
        source = await service.register_source(
            db,
            body=SourceRegisterRequest(
                source_id=body.source_id,
                title=body.name,
                source_type="website",
                visibility="guest",
                source_priority=body.source_priority,
                source_url=body.base_url,
            ),
            actor_user_id=user.id,
        )

    seed = WebsiteCrawlSeed(
        source_id=body.source_id,
        name=body.name,
        base_url=body.base_url,
        sitemap_url=body.sitemap_url,
        robots_url=body.robots_url,
        allowed_path_prefixes=body.allowed_path_prefixes,
        explicit_allow=body.explicit_allow,
        excluded_path_prefixes=body.excluded_path_prefixes,
        exclude_query_parameters=body.exclude_query_parameters,
        canonicalize_urls=body.canonicalize_urls,
        source_priority=body.source_priority,
    )
    crawl_run = await run_crawl(db, source=source, seed=seed, embedding_provider=embedding_provider)
    return success(CrawlRunOut.model_validate(crawl_run).model_dump(mode="json"))
