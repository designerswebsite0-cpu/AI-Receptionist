"""Phase 3: knowledge_source_versions

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-17

Every (re)processing run of a source produces a new version row rather
than overwriting extracted text in place — required for the brief's
versioning/audit requirements and for idempotent re-ingestion (a re-run
with an unchanged checksum should not create a new version at all; that
dedup logic lives in app.knowledge.service, not the schema).

raw_text/normalized_text are stored as TEXT rather than pushed to Storage:
document sizes in the RKPR corpus are small enough (largest source files
are low-single-digit MB) that Postgres TEXT is simpler and keeps versions
queryable without an extra storage round-trip. Revisit only if a much
larger corpus makes this a real size problem.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op
from app.knowledge.constants import PROCESSING_STATUSES

revision: str = "0012"
down_revision: str | None = "0011"
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
        "knowledge_source_versions",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "source_id", pg.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("storage_path", sa.String(1000), nullable=True),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("raw_text", sa.Text, nullable=True),
        sa.Column("normalized_text", sa.Text, nullable=True),
        sa.Column("page_count", sa.Integer, nullable=True),
        sa.Column("word_count", sa.Integer, nullable=True),
        sa.Column("extraction_method", sa.String(50), nullable=True),
        sa.Column("ocr_used", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("ocr_confidence", sa.Numeric(5, 2), nullable=True),
        sa.Column("processing_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.String(4000), nullable=True),
        sa.Column("is_current", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_by", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("source_id", "version_number", name="uq_knowledge_source_versions_source_version"),
        sa.CheckConstraint(f"processing_status IN {PROCESSING_STATUSES}", name="ck_knowledge_source_versions_status"),
    )
    op.create_index("ix_knowledge_source_versions_source_id", "knowledge_source_versions", ["source_id"])

    op.add_column(
        "knowledge_sources",
        sa.Column(
            "current_version_id", pg.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_source_versions.id", ondelete="SET NULL"), nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("knowledge_sources", "current_version_id")
    op.drop_index("ix_knowledge_source_versions_source_id", table_name="knowledge_source_versions")
    op.drop_table("knowledge_source_versions")
