import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TimestampMixin, UUIDPrimaryKeyMixin
from app.database import Base
from app.knowledge.constants import (
    APPROVAL_STATUSES,
    BENCHMARK_AUDIENCES,
    CHUNK_STATUSES,
    CHUNK_TYPES,
    CONFLICT_RESOLUTION_STATUSES,
    CRAWL_RUN_STATUSES,
    EMBEDDING_DIMENSIONS,
    FEEDBACK_RATINGS,
    JOB_STATUSES,
    JOB_TYPES,
    MEDIA_RIGHTS_STATUSES,
    PROCESSING_STATUSES,
    SOURCE_PRIORITY,
    SOURCE_STATUSES,
    SOURCE_TYPES,
    VISIBILITY,
)


class KnowledgeSource(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "knowledge_sources"
    __table_args__ = (
        CheckConstraint(f"source_type IN {SOURCE_TYPES}", name="ck_knowledge_sources_source_type"),
        CheckConstraint(f"visibility IN {VISIBILITY}", name="ck_knowledge_sources_visibility"),
        CheckConstraint(f"source_priority IN {SOURCE_PRIORITY}", name="ck_knowledge_sources_priority"),
        CheckConstraint(f"status IN {SOURCE_STATUSES}", name="ck_knowledge_sources_status"),
        CheckConstraint(f"approval_status IN {APPROVAL_STATUSES}", name="ck_knowledge_sources_approval_status"),
    )

    source_id: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    subcategory: Mapped[str | None] = mapped_column(String(100), nullable=True)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    storage_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(300), nullable=True)
    file_format: Mapped[str | None] = mapped_column(String(20), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    source_priority: Mapped[str] = mapped_column(String(20), nullable=False, default="normal")
    authoritative: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    retrieval_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    processing_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    ocr_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    malware_scan_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    approval_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    source_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        # use_alter breaks the knowledge_sources <-> knowledge_source_versions
        # cycle (each references the other) for DDL ordering purposes — CREATE/
        # DROP would otherwise be unsortable (SQLAlchemy raises
        # CircularDependencyError) since neither table can be created before
        # the other without this escape hatch. Name matches Postgres' own
        # default naming convention for this column (set by alembic migration
        # 0012, which didn't name it explicitly) so this stays a metadata-only
        # annotation — no migration/autogenerate diff against the real schema.
        ForeignKey(
            "knowledge_source_versions.id",
            ondelete="SET NULL",
            use_alter=True,
            name="knowledge_sources_current_version_id_fkey",
        ),
        nullable=True,
    )


class KnowledgeSourceVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "knowledge_source_versions"
    __table_args__ = (
        UniqueConstraint("source_id", "version_number", name="uq_knowledge_source_versions_source_version"),
        CheckConstraint(f"processing_status IN {PROCESSING_STATUSES}", name="ck_knowledge_source_versions_status"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extraction_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ocr_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ocr_confidence: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    processing_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class KnowledgeChunk(Base, UUIDPrimaryKeyMixin):
    """No TimestampMixin's onupdate semantics needed beyond created/updated;
    still uses the same two columns as every other table for consistency."""

    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("source_id", "chunk_key", name="uq_knowledge_chunks_source_chunk_key"),
        CheckConstraint(f"chunk_type IN {CHUNK_TYPES}", name="ck_knowledge_chunks_chunk_type"),
        CheckConstraint(f"visibility IN {VISIBILITY}", name="ck_knowledge_chunks_visibility"),
        CheckConstraint(f"source_priority IN {SOURCE_PRIORITY}", name="ck_knowledge_chunks_priority"),
        CheckConstraint(f"status IN {CHUNK_STATUSES}", name="ck_knowledge_chunks_status"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_source_versions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    chunk_key: Mapped[str] = mapped_column(String(128), nullable=False)
    chunk_type: Mapped[str] = mapped_column(String(30), nullable=False, default="generic", index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content_raw: Mapped[str] = mapped_column(Text, nullable=False)
    content_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    section_title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    heading_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entity_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    visibility: Mapped[str] = mapped_column(String(20), nullable=False)
    source_priority: Mapped[str] = mapped_column(String(20), nullable=False, default="normal")
    authoritative: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    retrieval_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class KnowledgeMedia(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "knowledge_media"
    __table_args__ = (
        CheckConstraint(f"rights_status IN {MEDIA_RIGHTS_STATUSES}", name="ck_knowledge_media_rights_status"),
        CheckConstraint(f"visibility IN {VISIBILITY}", name="ck_knowledge_media_visibility"),
    )

    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(300), nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    width_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    linked_entity: Mapped[str | None] = mapped_column(String(200), nullable=True)
    alt_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    caption: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    caption_is_inferred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rights_status: Mapped[str] = mapped_column(String(30), nullable=False, default="unknown")
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, default="guest")
    retrieval_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    media_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class KnowledgeIngestionJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "knowledge_ingestion_jobs"
    __table_args__ = (
        CheckConstraint(f"job_type IN {JOB_TYPES}", name="ck_knowledge_ingestion_jobs_type"),
        CheckConstraint(f"job_status IN {JOB_STATUSES}", name="ck_knowledge_ingestion_jobs_status"),
    )

    job_type: Mapped[str] = mapped_column(String(30), nullable=False)
    job_status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued", index=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    progress_current: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class KnowledgeRetrievalLog(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "knowledge_retrieval_logs"

    query_text: Mapped[str] = mapped_column(String(2000), nullable=False)
    query_classification: Mapped[str | None] = mapped_column(String(50), nullable=True)
    filters_applied: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    results_returned: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requested_channel: Mapped[str | None] = mapped_column(String(30), nullable=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class KnowledgeSearchFeedback(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "knowledge_search_feedback"
    __table_args__ = (CheckConstraint(f"rating IN {FEEDBACK_RATINGS}", name="ck_knowledge_search_feedback_rating"),)

    retrieval_log_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_retrieval_logs.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_chunks.id", ondelete="CASCADE"), nullable=True, index=True
    )
    rating: Mapped[str] = mapped_column(String(20), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class KnowledgeConflict(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "knowledge_conflicts"
    __table_args__ = (
        CheckConstraint(f"resolution_status IN {CONFLICT_RESOLUTION_STATUSES}", name="ck_knowledge_conflicts_status"),
    )

    conflict_key: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    description: Mapped[str] = mapped_column(String(4000), nullable=False)
    source_a_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_sources.id", ondelete="SET NULL"), nullable=True
    )
    source_b_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_sources.id", ondelete="SET NULL"), nullable=True
    )
    resolution_status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    resolution_notes: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    resolved_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_sources.id", ondelete="SET NULL"), nullable=True
    )


class KnowledgeBenchmarkQuestion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "knowledge_benchmark_questions"
    __table_args__ = (
        CheckConstraint(f"audience IN {BENCHMARK_AUDIENCES}", name="ck_knowledge_benchmark_audience"),
        CheckConstraint(f"priority IN {SOURCE_PRIORITY}", name="ck_knowledge_benchmark_priority"),
    )

    question: Mapped[str] = mapped_column(String(2000), nullable=False)
    expected_answer: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    expected_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_sources.id", ondelete="SET NULL"), nullable=True
    )
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    audience: Mapped[str] = mapped_column(String(20), nullable=False, default="guest", index=True)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="normal")
    last_run_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WebsiteCrawlRun(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "website_crawl_runs"
    __table_args__ = (CheckConstraint(f"run_status IN {CRAWL_RUN_STATUSES}", name="ck_website_crawl_runs_status"),)

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_status: Mapped[str] = mapped_column(String(20), nullable=False, default="running", index=True)
    pages_discovered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pages_crawled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pages_changed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pages_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    crawl_summary: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
