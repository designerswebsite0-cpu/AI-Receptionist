import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.knowledge.constants import SOURCE_PRIORITY, SOURCE_TYPES, VISIBILITY


def _validate_choice(value: str, allowed: tuple, field_name: str) -> str:
    if value not in allowed:
        raise ValueError(f"{field_name} must be one of {allowed}")
    return value


class SourceRegisterRequest(BaseModel):
    """Registers the governance shell for a knowledge source. File bytes
    are uploaded separately (multipart, handled by the router) — this
    creates the DB row the upload attaches to. `source_id` is the external
    register/manifest identifier (e.g. "SRC-001"), optional for ad-hoc
    dashboard uploads that have no register entry."""

    source_id: str | None = Field(default=None, max_length=50)
    title: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=4000)
    source_type: str
    category: str | None = Field(default=None, max_length=100)
    subcategory: str | None = Field(default=None, max_length=100)
    language: str = "en"
    visibility: str
    source_priority: str = "normal"
    authoritative: bool = False
    ocr_required: bool = False
    effective_date: date | None = None
    expiry_date: date | None = None
    source_url: str | None = Field(default=None, max_length=1000)
    tags: list[str] = Field(default_factory=list)
    source_metadata: dict = Field(default_factory=dict)

    @field_validator("source_type")
    @classmethod
    def _v_source_type(cls, value: str) -> str:
        return _validate_choice(value, SOURCE_TYPES, "source_type")

    @field_validator("visibility")
    @classmethod
    def _v_visibility(cls, value: str) -> str:
        return _validate_choice(value, VISIBILITY, "visibility")

    @field_validator("source_priority")
    @classmethod
    def _v_priority(cls, value: str) -> str:
        return _validate_choice(value, SOURCE_PRIORITY, "source_priority")


class SourceGovernanceUpdateRequest(BaseModel):
    """Partial update of governance fields only — content/processing
    fields are written exclusively by the ingestion pipeline, never by a
    dashboard PATCH, so they're deliberately absent from this schema."""

    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=4000)
    category: str | None = None
    subcategory: str | None = None
    visibility: str | None = None
    source_priority: str | None = None
    authoritative: bool | None = None
    effective_date: date | None = None
    expiry_date: date | None = None
    tags: list[str] | None = None

    @field_validator("visibility")
    @classmethod
    def _v_visibility(cls, value: str | None) -> str | None:
        return value if value is None else _validate_choice(value, VISIBILITY, "visibility")

    @field_validator("source_priority")
    @classmethod
    def _v_priority(cls, value: str | None) -> str | None:
        return value if value is None else _validate_choice(value, SOURCE_PRIORITY, "source_priority")


class SourceRejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class SourceOut(BaseModel):
    id: uuid.UUID
    source_id: str | None
    title: str
    description: str | None
    source_type: str
    category: str | None
    subcategory: str | None
    language: str
    storage_path: str | None
    original_filename: str | None
    file_format: str | None
    mime_type: str | None
    file_size_bytes: int | None
    checksum_sha256: str | None
    source_url: str | None
    visibility: str
    source_priority: str
    authoritative: bool
    retrieval_enabled: bool
    status: str
    processing_status: str
    ocr_required: bool
    malware_scan_status: str
    approval_status: str
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    effective_date: date | None
    expiry_date: date | None
    tags: list[str]
    current_version_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SourceListResponse(BaseModel):
    items: list[SourceOut]
    total: int
    offset: int
    limit: int


class SourceVersionOut(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    version_number: int
    storage_path: str | None
    checksum_sha256: str
    page_count: int | None
    word_count: int | None
    extraction_method: str | None
    ocr_used: bool
    ocr_confidence: float | None
    processing_status: str
    error_message: str | None
    is_current: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MediaOut(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID | None
    storage_path: str
    original_filename: str | None
    mime_type: str | None
    width_px: int | None
    height_px: int | None
    category: str | None
    linked_entity: str | None
    alt_text: str | None
    caption: str | None
    caption_is_inferred: bool
    rights_status: str
    visibility: str
    retrieval_enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class IngestionJobOut(BaseModel):
    id: uuid.UUID
    job_type: str
    job_status: str
    source_id: uuid.UUID | None
    progress_current: int
    progress_total: int | None
    result_summary: dict | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    items: list[IngestionJobOut]
    total: int
    offset: int
    limit: int


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    guest_only: bool = True
    limit: int = Field(default=10, ge=1, le=50)
    chunk_type: str | None = None
    conversation_id: uuid.UUID | None = None
    requested_channel: str | None = None


class CitationOut(BaseModel):
    """What a caller (the future answer composer, or the dashboard's
    search playground) is allowed to see about a retrieved chunk. Never
    includes storage_path or any internal file location — citations are
    built from source title/id/version/section/date/priority only, per
    the brief's citation requirements."""

    chunk_id: uuid.UUID
    content: str
    chunk_type: str
    section_title: str | None
    page_number: int | None
    source_id: uuid.UUID
    source_external_id: str | None
    source_title: str
    source_priority: str
    authoritative: bool
    version_number: int | None
    effective_date: date | None
    source_url: str | None
    score: float


class SearchResponse(BaseModel):
    query: str
    query_classification: str
    results: list[CitationOut]
    retrieval_log_id: uuid.UUID
    latency_ms: int


class WebsiteCrawlRequest(BaseModel):
    """Mirrors website_crawl_seed.json's shape — the dashboard manages
    this config for a website source and triggers a crawl with it,
    rather than the crawler reading a file path directly (this is an
    HTTP API, not the CLI import script)."""

    source_id: str
    name: str
    base_url: str
    sitemap_url: str
    robots_url: str
    allowed_path_prefixes: list[str] = Field(default_factory=list)
    explicit_allow: list[str] = Field(default_factory=list)
    excluded_path_prefixes: list[str] = Field(default_factory=list)
    exclude_query_parameters: bool = True
    canonicalize_urls: bool = True
    source_priority: str = "normal"


class CrawlRunOut(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    run_status: str
    pages_discovered: int
    pages_crawled: int
    pages_changed: int
    pages_failed: int
    started_at: datetime
    completed_at: datetime | None
    crawl_summary: list

    model_config = {"from_attributes": True}
