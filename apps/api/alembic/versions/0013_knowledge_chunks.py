"""Phase 3: knowledge_chunks (pgvector)

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-17

The retrieval unit. Governance columns (visibility, source_priority,
authoritative, retrieval_enabled, effective_date, expiry_date) are
denormalized from knowledge_sources onto each chunk at chunk-creation time
so the guest-facing retrieval query (IMPLEMENTATION_PLAN.md §2) can filter
and score in a single index scan without joining knowledge_sources on
every request. app.knowledge.service re-syncs these whenever a source's
governance fields change (approval, archival, expiry).

embedding is nullable: a chunk exists (and is full-text searchable) as
soon as it's created by the chunker, before the embedding stage runs.
HNSW index is built after the column exists rather than inline, since
pgvector requires at least one row for cost estimation to be meaningful
and an empty-table index is still valid but this ordering matches how the
ingestion pipeline will actually populate the table.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql as pg

from alembic import op
from app.knowledge.constants import CHUNK_STATUSES, CHUNK_TYPES, EMBEDDING_DIMENSIONS, SOURCE_PRIORITY, VISIBILITY

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "source_id", pg.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "version_id", pg.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_source_versions.id", ondelete="CASCADE"), nullable=False,
        ),
        # Deterministic key (source_id + structural position + content
        # hash) so re-ingesting an unchanged source produces byte-identical
        # keys and the embedding step can skip unchanged chunks.
        sa.Column("chunk_key", sa.String(128), nullable=False),
        sa.Column("chunk_type", sa.String(30), nullable=False, server_default="generic"),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content_raw", sa.Text, nullable=False),
        sa.Column("content_normalized", sa.Text, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("section_title", sa.String(300), nullable=True),
        sa.Column("heading_path", sa.String(500), nullable=True),
        sa.Column("page_number", sa.Integer, nullable=True),
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSIONS), nullable=True),
        sa.Column("embedding_model", sa.String(100), nullable=True),
        sa.Column("entity_metadata", pg.JSONB, nullable=False, server_default="{}"),
        # --- denormalized governance (see module docstring) ---
        sa.Column("visibility", sa.String(20), nullable=False),
        sa.Column("source_priority", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("authoritative", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("retrieval_enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("effective_date", sa.Date, nullable=True),
        sa.Column("expiry_date", sa.Date, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
            onupdate=sa.func.now(), nullable=False,
        ),
        sa.UniqueConstraint("source_id", "chunk_key", name="uq_knowledge_chunks_source_chunk_key"),
        sa.CheckConstraint(f"chunk_type IN {CHUNK_TYPES}", name="ck_knowledge_chunks_chunk_type"),
        sa.CheckConstraint(f"visibility IN {VISIBILITY}", name="ck_knowledge_chunks_visibility"),
        sa.CheckConstraint(f"source_priority IN {SOURCE_PRIORITY}", name="ck_knowledge_chunks_priority"),
        sa.CheckConstraint(f"status IN {CHUNK_STATUSES}", name="ck_knowledge_chunks_status"),
    )
    op.create_index("ix_knowledge_chunks_source_id", "knowledge_chunks", ["source_id"])
    op.create_index("ix_knowledge_chunks_version_id", "knowledge_chunks", ["version_id"])
    op.create_index("ix_knowledge_chunks_chunk_type", "knowledge_chunks", ["chunk_type"])
    # The guest-safety composite: every guest retrieval query filters on
    # exactly these three columns before scoring anything.
    op.create_index(
        "ix_knowledge_chunks_guest_filter", "knowledge_chunks",
        ["visibility", "retrieval_enabled", "status"],
    )
    op.execute(
        "CREATE INDEX ix_knowledge_chunks_fts ON knowledge_chunks "
        "USING gin (to_tsvector('english', content_normalized))"
    )
    op.execute(
        "CREATE INDEX ix_knowledge_chunks_embedding_hnsw ON knowledge_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_fts")
    op.drop_index("ix_knowledge_chunks_guest_filter", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_chunk_type", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_version_id", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_source_id", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
