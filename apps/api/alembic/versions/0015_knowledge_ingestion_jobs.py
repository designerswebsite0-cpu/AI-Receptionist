"""Phase 3: knowledge_ingestion_jobs

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-17

Durable job-tracking row for every pipeline run, written identically
whether app.knowledge.jobs picks RedisIngestionQueue or
InlineIngestionQueue as the executor (IMPLEMENTATION_PLAN.md §4) — the
dashboard's job/progress views read only this table, never the queue
backend directly.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op
from app.knowledge.constants import JOB_STATUSES, JOB_TYPES

revision: str = "0015"
down_revision: str | None = "0014"
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
        "knowledge_ingestion_jobs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_type", sa.String(30), nullable=False),
        sa.Column("job_status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column(
            "source_id", pg.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_sources.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("payload", pg.JSONB, nullable=False, server_default="{}"),
        sa.Column("progress_current", sa.Integer, nullable=False, server_default="0"),
        sa.Column("progress_total", sa.Integer, nullable=True),
        sa.Column("result_summary", pg.JSONB, nullable=True),
        sa.Column("error_message", sa.String(4000), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("worker_id", sa.String(100), nullable=True),
        sa.Column("created_by", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(f"job_type IN {JOB_TYPES}", name="ck_knowledge_ingestion_jobs_type"),
        sa.CheckConstraint(f"job_status IN {JOB_STATUSES}", name="ck_knowledge_ingestion_jobs_status"),
    )
    op.create_index("ix_knowledge_ingestion_jobs_status", "knowledge_ingestion_jobs", ["job_status"])
    op.create_index("ix_knowledge_ingestion_jobs_source_id", "knowledge_ingestion_jobs", ["source_id"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_ingestion_jobs_source_id", table_name="knowledge_ingestion_jobs")
    op.drop_index("ix_knowledge_ingestion_jobs_status", table_name="knowledge_ingestion_jobs")
    op.drop_table("knowledge_ingestion_jobs")
