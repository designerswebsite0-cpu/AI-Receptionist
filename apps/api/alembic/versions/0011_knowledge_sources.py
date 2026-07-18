"""Phase 3: knowledge_sources

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-17

One row per governed knowledge asset (a PDF, a website registration, a
media item's parent record, a dataset). Governance fields (visibility,
source_priority, authoritative, approval_status) come from the Knowledge
Source Register and drive both ingestion eligibility and retrieval
filtering — see docs/phase-3/IMPLEMENTATION_PLAN.md §1-2.

current_version_id is added by 0012 (knowledge_source_versions) once that
table exists, avoiding a forward reference here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op
from app.knowledge.constants import (
    APPROVAL_STATUSES,
    SOURCE_PRIORITY,
    SOURCE_STATUSES,
    SOURCE_TYPES,
    VISIBILITY,
)

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
            onupdate=sa.func.now(), nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "knowledge_sources",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        # External stable identifier from the governance register or
        # website_crawl_seed.json (e.g. "SRC-001", "WEB-RKPR-001"). Nullable
        # because ad-hoc dashboard uploads outside the RKPR corpus won't
        # have a register entry.
        sa.Column("source_id", sa.String(50), nullable=True, unique=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.String(4000), nullable=True),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("subcategory", sa.String(100), nullable=True),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("storage_path", sa.String(1000), nullable=True),
        sa.Column("original_filename", sa.String(300), nullable=True),
        sa.Column("file_format", sa.String(20), nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger, nullable=True),
        sa.Column("checksum_sha256", sa.String(64), nullable=True),
        sa.Column("source_url", sa.String(1000), nullable=True),
        sa.Column("visibility", sa.String(20), nullable=False),
        sa.Column("source_priority", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("authoritative", sa.Boolean, nullable=False, server_default=sa.false()),
        # Governance/DB-level guest-safety gate — see IMPLEMENTATION_PLAN.md
        # §2: every guest-facing query filters on this directly, never a
        # post-filter or prompt instruction.
        sa.Column("retrieval_enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("processing_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("ocr_required", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("malware_scan_status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("approval_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("approved_by", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_date", sa.Date, nullable=True),
        sa.Column("expiry_date", sa.Date, nullable=True),
        sa.Column("tags", pg.JSONB, nullable=False, server_default="[]"),
        # Raw governance-register row / manifest row / crawl-seed JSON,
        # preserved verbatim for audit/debugging of the matching process.
        sa.Column("source_metadata", pg.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_by", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(f"source_type IN {SOURCE_TYPES}", name="ck_knowledge_sources_source_type"),
        sa.CheckConstraint(f"visibility IN {VISIBILITY}", name="ck_knowledge_sources_visibility"),
        sa.CheckConstraint(f"source_priority IN {SOURCE_PRIORITY}", name="ck_knowledge_sources_priority"),
        sa.CheckConstraint(f"status IN {SOURCE_STATUSES}", name="ck_knowledge_sources_status"),
        sa.CheckConstraint(f"approval_status IN {APPROVAL_STATUSES}", name="ck_knowledge_sources_approval_status"),
    )
    op.create_index("ix_knowledge_sources_source_type", "knowledge_sources", ["source_type"])
    op.create_index("ix_knowledge_sources_visibility", "knowledge_sources", ["visibility"])
    op.create_index("ix_knowledge_sources_status", "knowledge_sources", ["status"])
    op.create_index("ix_knowledge_sources_checksum_sha256", "knowledge_sources", ["checksum_sha256"])
    # Trigram index for fuzzy filename/title matching in the governance
    # importer's multi-strategy matcher (pg_trgm, enabled in 0010).
    op.execute(
        "CREATE INDEX ix_knowledge_sources_title_trgm ON knowledge_sources "
        "USING gin (title gin_trgm_ops)"
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_sources_title_trgm", table_name="knowledge_sources")
    op.drop_index("ix_knowledge_sources_checksum_sha256", table_name="knowledge_sources")
    op.drop_index("ix_knowledge_sources_status", table_name="knowledge_sources")
    op.drop_index("ix_knowledge_sources_visibility", table_name="knowledge_sources")
    op.drop_index("ix_knowledge_sources_source_type", table_name="knowledge_sources")
    op.drop_table("knowledge_sources")
