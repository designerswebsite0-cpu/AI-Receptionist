"""Phase 3: enable pgvector, pg_trgm, unaccent extensions

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-17

Confirmed available on the connected Supabase project (pgvector 0.8.2,
pg_trgm, unaccent) via a live audit query before this migration was
written. pgvector backs knowledge_chunks.embedding (0013); pg_trgm and
unaccent back fuzzy filename/title matching in the governance importer
(app.knowledge.governance.matching) and improve full-text search quality
against accented resort/menu terms.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")


def downgrade() -> None:
    # Never drop extensions on downgrade — other objects (indexes, columns)
    # created in later migrations depend on them, and downgrading migrations
    # in order will drop those dependents first.
    pass
