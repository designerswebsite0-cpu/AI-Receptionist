"""Phase 3: RLS for knowledge tables

Revision ID: 0019
Revises: 0018
Create Date: 2026-07-17

Same defense-in-depth pattern as 0009_single_resort_rls.py: any
authenticated user may read/write via direct-Postgres access paths, since
this is a single-resort deployment with no role distinctions
(docs/CLAUDE.md "Single-Resort Access Model"). This is NOT the guest-safety
boundary — the FastAPI backend's retrieval query (WHERE visibility='guest'
AND retrieval_enabled AND status='active', see 0013's chunks table) is the
real gate for what an anonymous guest-facing channel can retrieve, and it
runs under the service_role connection which bypasses RLS entirely. RLS
here only protects against a stray direct-Postgres client (e.g. Supabase
Realtime) reading/writing without any authentication at all.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_AUTHENTICATED = "auth.uid() IS NOT NULL"

_TABLES = [
    "knowledge_sources",
    "knowledge_source_versions",
    "knowledge_chunks",
    "knowledge_media",
    "knowledge_ingestion_jobs",
    "knowledge_retrieval_logs",
    "knowledge_search_feedback",
    "knowledge_conflicts",
    "knowledge_benchmark_questions",
    "website_crawl_runs",
]


def upgrade() -> None:
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_select ON {table} FOR SELECT
            USING ({_AUTHENTICATED})
            """
        )
        op.execute(
            f"""
            CREATE POLICY {table}_modify ON {table} FOR ALL
            USING ({_AUTHENTICATED})
            WITH CHECK ({_AUTHENTICATED})
            """
        )


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"DROP POLICY IF EXISTS {table}_modify ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_select ON {table}")
