"""Phase 3: knowledge_media

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-17

Images (room photos, spa photos, menu photos) with rights/caption
metadata. Distinct from knowledge_sources because a single PDF source can
yield many extracted images, and standalone image files in
02_MEDIA_INDEXABLE have no "document" to extract from — both cases need
one row per image, optionally linked back to a parent source.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op
from app.knowledge.constants import MEDIA_RIGHTS_STATUSES, VISIBILITY

revision: str = "0014"
down_revision: str | None = "0013"
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
        "knowledge_media",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "source_id", pg.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_sources.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("storage_path", sa.String(1000), nullable=False),
        sa.Column("original_filename", sa.String(300), nullable=True),
        sa.Column("checksum_sha256", sa.String(64), nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("width_px", sa.Integer, nullable=True),
        sa.Column("height_px", sa.Integer, nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger, nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("linked_entity", sa.String(200), nullable=True),
        sa.Column("alt_text", sa.String(500), nullable=True),
        sa.Column("caption", sa.String(1000), nullable=True),
        sa.Column("caption_is_inferred", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("rights_status", sa.String(30), nullable=False, server_default="unknown"),
        sa.Column("visibility", sa.String(20), nullable=False, server_default="guest"),
        sa.Column("retrieval_enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("media_metadata", pg.JSONB, nullable=False, server_default="{}"),
        *_timestamps(),
        sa.CheckConstraint(f"rights_status IN {MEDIA_RIGHTS_STATUSES}", name="ck_knowledge_media_rights_status"),
        sa.CheckConstraint(f"visibility IN {VISIBILITY}", name="ck_knowledge_media_visibility"),
    )
    op.create_index("ix_knowledge_media_source_id", "knowledge_media", ["source_id"])
    op.create_index("ix_knowledge_media_category", "knowledge_media", ["category"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_media_category", table_name="knowledge_media")
    op.drop_index("ix_knowledge_media_source_id", table_name="knowledge_media")
    op.drop_table("knowledge_media")
