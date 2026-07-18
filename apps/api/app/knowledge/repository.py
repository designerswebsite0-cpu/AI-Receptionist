import uuid

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge.models import (
    KnowledgeBenchmarkQuestion,
    KnowledgeChunk,
    KnowledgeConflict,
    KnowledgeIngestionJob,
    KnowledgeMedia,
    KnowledgeRetrievalLog,
    KnowledgeSource,
    KnowledgeSourceVersion,
    WebsiteCrawlRun,
)

# --- knowledge_sources -------------------------------------------------------


async def get_source(db: AsyncSession, source_id: uuid.UUID) -> KnowledgeSource | None:
    result = await db.execute(select(KnowledgeSource).where(KnowledgeSource.id == source_id))
    return result.scalar_one_or_none()


async def get_source_by_external_id(db: AsyncSession, source_id: str) -> KnowledgeSource | None:
    result = await db.execute(select(KnowledgeSource).where(KnowledgeSource.source_id == source_id))
    return result.scalar_one_or_none()


async def get_source_by_checksum(db: AsyncSession, checksum: str) -> KnowledgeSource | None:
    result = await db.execute(select(KnowledgeSource).where(KnowledgeSource.checksum_sha256 == checksum))
    return result.scalar_one_or_none()


async def get_sources_by_ids(db: AsyncSession, source_ids: list[uuid.UUID]) -> dict[uuid.UUID, KnowledgeSource]:
    if not source_ids:
        return {}
    result = await db.execute(select(KnowledgeSource).where(KnowledgeSource.id.in_(source_ids)))
    return {source.id: source for source in result.scalars().all()}


async def list_sources(
    db: AsyncSession,
    *,
    source_type: str | None = None,
    visibility: str | None = None,
    status: str | None = None,
    search: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[KnowledgeSource], int]:
    query = select(KnowledgeSource)
    count_query = select(func.count()).select_from(KnowledgeSource)

    conditions = []
    if source_type:
        conditions.append(KnowledgeSource.source_type == source_type)
    if visibility:
        conditions.append(KnowledgeSource.visibility == visibility)
    if status:
        conditions.append(KnowledgeSource.status == status)
    if search:
        pattern = f"%{search}%"
        conditions.append(or_(KnowledgeSource.title.ilike(pattern), KnowledgeSource.source_id.ilike(pattern)))

    for condition in conditions:
        query = query.where(condition)
        count_query = count_query.where(condition)

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(query.order_by(KnowledgeSource.created_at.desc()).offset(offset).limit(limit))
    return list(result.scalars().all()), total


# --- knowledge_source_versions ------------------------------------------------


async def get_version(db: AsyncSession, version_id: uuid.UUID) -> KnowledgeSourceVersion | None:
    result = await db.execute(select(KnowledgeSourceVersion).where(KnowledgeSourceVersion.id == version_id))
    return result.scalar_one_or_none()


async def list_versions(db: AsyncSession, source_id: uuid.UUID) -> list[KnowledgeSourceVersion]:
    result = await db.execute(
        select(KnowledgeSourceVersion)
        .where(KnowledgeSourceVersion.source_id == source_id)
        .order_by(KnowledgeSourceVersion.version_number.desc())
    )
    return list(result.scalars().all())


async def get_latest_version_number(db: AsyncSession, source_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.max(KnowledgeSourceVersion.version_number)).where(
            KnowledgeSourceVersion.source_id == source_id
        )
    )
    return result.scalar_one() or 0


async def clear_current_version_flag(db: AsyncSession, source_id: uuid.UUID) -> None:
    await db.execute(
        update(KnowledgeSourceVersion)
        .where(KnowledgeSourceVersion.source_id == source_id, KnowledgeSourceVersion.is_current.is_(True))
        .values(is_current=False)
    )


# --- knowledge_chunks (governance sync only — retrieval queries live in
# app.knowledge.retrieval, built in a later Phase 3 step) -------------------


async def sync_chunk_governance(db: AsyncSession, source: KnowledgeSource) -> None:
    """Propagates a source's current governance fields onto its existing
    chunks. Called whenever those fields change (approval, archival,
    visibility edits) — chunks denormalize these columns for guest-query
    performance (see migration 0013's docstring), so they'd otherwise go
    stale the moment a source is re-governed after chunking already ran.
    A no-op before any chunks exist, which is fine — chunk creation reads
    the parent source's current values directly."""
    await db.execute(
        update(KnowledgeChunk)
        .where(KnowledgeChunk.source_id == source.id)
        .values(
            visibility=source.visibility,
            source_priority=source.source_priority,
            authoritative=source.authoritative,
            retrieval_enabled=source.retrieval_enabled,
            effective_date=source.effective_date,
            expiry_date=source.expiry_date,
        )
    )


async def list_chunks_for_source(db: AsyncSession, source_id: uuid.UUID) -> list[KnowledgeChunk]:
    result = await db.execute(select(KnowledgeChunk).where(KnowledgeChunk.source_id == source_id))
    return list(result.scalars().all())


async def delete_chunks_by_ids(db: AsyncSession, chunk_ids: list[uuid.UUID]) -> None:
    if not chunk_ids:
        return
    await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.id.in_(chunk_ids)))


# --- knowledge_media ----------------------------------------------------------


async def list_media(db: AsyncSession, source_id: uuid.UUID) -> list[KnowledgeMedia]:
    result = await db.execute(select(KnowledgeMedia).where(KnowledgeMedia.source_id == source_id))
    return list(result.scalars().all())


async def get_media(db: AsyncSession, media_id: uuid.UUID) -> KnowledgeMedia | None:
    result = await db.execute(select(KnowledgeMedia).where(KnowledgeMedia.id == media_id))
    return result.scalar_one_or_none()


# --- knowledge_ingestion_jobs -------------------------------------------------


async def get_job(db: AsyncSession, job_id: uuid.UUID) -> KnowledgeIngestionJob | None:
    result = await db.execute(select(KnowledgeIngestionJob).where(KnowledgeIngestionJob.id == job_id))
    return result.scalar_one_or_none()


async def list_jobs(
    db: AsyncSession,
    *,
    job_type: str | None = None,
    job_status: str | None = None,
    source_id: uuid.UUID | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[KnowledgeIngestionJob], int]:
    query = select(KnowledgeIngestionJob)
    count_query = select(func.count()).select_from(KnowledgeIngestionJob)

    conditions = []
    if job_type:
        conditions.append(KnowledgeIngestionJob.job_type == job_type)
    if job_status:
        conditions.append(KnowledgeIngestionJob.job_status == job_status)
    if source_id:
        conditions.append(KnowledgeIngestionJob.source_id == source_id)

    for condition in conditions:
        query = query.where(condition)
        count_query = count_query.where(condition)

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(query.order_by(KnowledgeIngestionJob.created_at.desc()).offset(offset).limit(limit))
    return list(result.scalars().all()), total


# --- knowledge_retrieval_logs --------------------------------------------------


async def get_retrieval_log(db: AsyncSession, log_id: uuid.UUID) -> KnowledgeRetrievalLog | None:
    result = await db.execute(select(KnowledgeRetrievalLog).where(KnowledgeRetrievalLog.id == log_id))
    return result.scalar_one_or_none()


async def create_retrieval_log(
    db: AsyncSession,
    *,
    query_text: str,
    query_classification: str | None,
    filters_applied: dict,
    results_returned: list,
    latency_ms: int | None,
    requested_channel: str | None,
    conversation_id: uuid.UUID | None,
    requested_by: uuid.UUID | None,
) -> KnowledgeRetrievalLog:
    log = KnowledgeRetrievalLog(
        query_text=query_text,
        query_classification=query_classification,
        filters_applied=filters_applied,
        results_returned=results_returned,
        result_count=len(results_returned),
        latency_ms=latency_ms,
        requested_channel=requested_channel,
        conversation_id=conversation_id,
        requested_by=requested_by,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


# --- knowledge_conflicts / knowledge_benchmark_questions (governance import) -


async def get_conflict_by_key(db: AsyncSession, conflict_key: str) -> KnowledgeConflict | None:
    result = await db.execute(select(KnowledgeConflict).where(KnowledgeConflict.conflict_key == conflict_key))
    return result.scalar_one_or_none()


async def get_benchmark_question_by_text(db: AsyncSession, question: str) -> KnowledgeBenchmarkQuestion | None:
    result = await db.execute(
        select(KnowledgeBenchmarkQuestion).where(KnowledgeBenchmarkQuestion.question == question)
    )
    return result.scalar_one_or_none()


# --- website_crawl_runs -----------------------------------------------------


async def get_latest_crawl_run(db: AsyncSession, source_id: uuid.UUID) -> WebsiteCrawlRun | None:
    result = await db.execute(
        select(WebsiteCrawlRun)
        .where(WebsiteCrawlRun.source_id == source_id, WebsiteCrawlRun.run_status == "completed")
        .order_by(WebsiteCrawlRun.started_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def create_crawl_run(db: AsyncSession, *, source_id: uuid.UUID) -> WebsiteCrawlRun:
    run = WebsiteCrawlRun(source_id=source_id, run_status="running")
    db.add(run)
    await db.flush()
    return run
