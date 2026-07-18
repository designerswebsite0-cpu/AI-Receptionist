"""Phase 3: knowledge_retrieval_logs, knowledge_search_feedback

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-17

Every retrieval call (live conversation, dashboard search playground, or
benchmark run) writes a log row — required for the brief's analytics
requirements and for the benchmark evaluator to score itself against
known-good questions. Feedback is a separate table so staff can rate a
specific chunk's usefulness after the fact without mutating the log.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op
from app.knowledge.constants import FEEDBACK_RATINGS

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_retrieval_logs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("query_text", sa.String(2000), nullable=False),
        sa.Column("query_classification", sa.String(50), nullable=True),
        sa.Column("filters_applied", pg.JSONB, nullable=False, server_default="{}"),
        sa.Column("results_returned", pg.JSONB, nullable=False, server_default="[]"),
        sa.Column("result_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("requested_channel", sa.String(30), nullable=True),
        sa.Column(
            "conversation_id", pg.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("requested_by", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_knowledge_retrieval_logs_conversation_id", "knowledge_retrieval_logs", ["conversation_id"])
    op.create_index("ix_knowledge_retrieval_logs_created_at", "knowledge_retrieval_logs", ["created_at"])

    op.create_table(
        "knowledge_search_feedback",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "retrieval_log_id", pg.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_retrieval_logs.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "chunk_id", pg.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_chunks.id", ondelete="CASCADE"), nullable=True,
        ),
        sa.Column("rating", sa.String(20), nullable=False),
        sa.Column("notes", sa.String(2000), nullable=True),
        sa.Column("created_by", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(f"rating IN {FEEDBACK_RATINGS}", name="ck_knowledge_search_feedback_rating"),
    )
    op.create_index("ix_knowledge_search_feedback_retrieval_log_id", "knowledge_search_feedback", ["retrieval_log_id"])
    op.create_index("ix_knowledge_search_feedback_chunk_id", "knowledge_search_feedback", ["chunk_id"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_search_feedback_chunk_id", table_name="knowledge_search_feedback")
    op.drop_index("ix_knowledge_search_feedback_retrieval_log_id", table_name="knowledge_search_feedback")
    op.drop_table("knowledge_search_feedback")
    op.drop_index("ix_knowledge_retrieval_logs_created_at", table_name="knowledge_retrieval_logs")
    op.drop_index("ix_knowledge_retrieval_logs_conversation_id", table_name="knowledge_retrieval_logs")
    op.drop_table("knowledge_retrieval_logs")
