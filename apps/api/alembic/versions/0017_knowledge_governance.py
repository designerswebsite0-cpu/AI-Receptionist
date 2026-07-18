"""Phase 3: knowledge_conflicts, knowledge_benchmark_questions

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-17

Mirrors RKPR_RAG_FINAL_DOCS/04_GOVERNANCE/Conflicting_Information_Register.xlsx
(CON-001 etc.) and Common_Guest_Questions_Dataset.xlsx respectively — both
imported by app.knowledge.governance.importer, both also usable for
ad-hoc entries created from the dashboard after Phase 3 ships.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op
from app.knowledge.constants import BENCHMARK_AUDIENCES, CONFLICT_RESOLUTION_STATUSES, SOURCE_PRIORITY

revision: str = "0017"
down_revision: str | None = "0016"
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
        "knowledge_conflicts",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("conflict_key", sa.String(50), nullable=True, unique=True),
        sa.Column("description", sa.String(4000), nullable=False),
        sa.Column(
            "source_a_id", pg.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_sources.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "source_b_id", pg.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_sources.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("resolution_status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("resolution_notes", sa.String(4000), nullable=True),
        sa.Column(
            "resolved_source_id", pg.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_sources.id", ondelete="SET NULL"), nullable=True,
        ),
        *_timestamps(),
        sa.CheckConstraint(
            f"resolution_status IN {CONFLICT_RESOLUTION_STATUSES}", name="ck_knowledge_conflicts_status"
        ),
    )
    op.create_index("ix_knowledge_conflicts_resolution_status", "knowledge_conflicts", ["resolution_status"])

    op.create_table(
        "knowledge_benchmark_questions",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("question", sa.String(2000), nullable=False),
        sa.Column("expected_answer", sa.String(4000), nullable=True),
        sa.Column(
            "expected_source_id", pg.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_sources.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("audience", sa.String(20), nullable=False, server_default="guest"),
        sa.Column("priority", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("last_run_result", pg.JSONB, nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(f"audience IN {BENCHMARK_AUDIENCES}", name="ck_knowledge_benchmark_audience"),
        sa.CheckConstraint(f"priority IN {SOURCE_PRIORITY}", name="ck_knowledge_benchmark_priority"),
    )
    op.create_index("ix_knowledge_benchmark_questions_audience", "knowledge_benchmark_questions", ["audience"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_benchmark_questions_audience", table_name="knowledge_benchmark_questions")
    op.drop_table("knowledge_benchmark_questions")
    op.drop_index("ix_knowledge_conflicts_resolution_status", table_name="knowledge_conflicts")
    op.drop_table("knowledge_conflicts")
