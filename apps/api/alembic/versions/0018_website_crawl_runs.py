"""Phase 3: website_crawl_runs

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-17

One row per crawl execution of the resort website source (WEB-RKPR-001).
crawl_summary holds the per-page results (url, canonical_url, http_status,
content_hash, chunk_count) required by
RKPR_RAG_FINAL_DOCS/00_CONTROL/WEBSITE_SOURCE_ADDITION_REPORT.md's
acceptance condition, so a completed run is self-documenting evidence of
what was actually fetched.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op
from app.knowledge.constants import CRAWL_RUN_STATUSES

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "website_crawl_runs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "source_id", pg.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("run_status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("pages_discovered", sa.Integer, nullable=False, server_default="0"),
        sa.Column("pages_crawled", sa.Integer, nullable=False, server_default="0"),
        sa.Column("pages_changed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("pages_failed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.String(4000), nullable=True),
        sa.Column("crawl_summary", pg.JSONB, nullable=False, server_default="[]"),
        sa.CheckConstraint(f"run_status IN {CRAWL_RUN_STATUSES}", name="ck_website_crawl_runs_status"),
    )
    op.create_index("ix_website_crawl_runs_source_id", "website_crawl_runs", ["source_id"])
    op.create_index("ix_website_crawl_runs_status", "website_crawl_runs", ["run_status"])


def downgrade() -> None:
    op.drop_index("ix_website_crawl_runs_status", table_name="website_crawl_runs")
    op.drop_index("ix_website_crawl_runs_source_id", table_name="website_crawl_runs")
    op.drop_table("website_crawl_runs")
