"""Phase 4: orchestration_turns

Revision ID: 0021
Revises: 0020
Create Date: 2026-07-18

One row per AI pipeline run — the decision trace (intent/entities/
retrieval/tool/handoff/validation/provider), never chain-of-thought. See
docs/phase-4/PHASE_4_IMPLEMENTATION_PLAN.md §2.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "orchestration_turns",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_id", pg.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "message_id", pg.UUID(as_uuid=True), sa.ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "response_message_id", pg.UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("detected_intent", sa.String(50), nullable=True),
        sa.Column("intent_confidence", sa.Float, nullable=True),
        sa.Column("secondary_intents", pg.JSONB, nullable=False, server_default="[]"),
        sa.Column("extracted_entities", pg.JSONB, nullable=False, server_default="{}"),
        sa.Column("missing_entities", pg.JSONB, nullable=False, server_default="[]"),
        sa.Column("flow_state", sa.String(50), nullable=True),
        sa.Column("retrieval_query", sa.String(2000), nullable=True),
        sa.Column("citations", pg.JSONB, nullable=False, server_default="[]"),
        sa.Column("tool_name", sa.String(50), nullable=True),
        sa.Column("tool_input", pg.JSONB, nullable=False, server_default="{}"),
        sa.Column("tool_output", pg.JSONB, nullable=True),
        sa.Column("tool_status", sa.String(20), nullable=True),
        sa.Column("handoff_required", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("handoff_reason", sa.String(50), nullable=True),
        sa.Column("handoff_priority", sa.String(20), nullable=True),
        sa.Column("handoff_department", sa.String(50), nullable=True),
        sa.Column("validation_result", pg.JSONB, nullable=False, server_default="{}"),
        sa.Column("provider_used", sa.String(30), nullable=True),
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("token_usage", pg.JSONB, nullable=False, server_default="{}"),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("error_message", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_orchestration_turns_conversation_id", "orchestration_turns", ["conversation_id"])
    op.create_index("ix_orchestration_turns_created_at", "orchestration_turns", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_orchestration_turns_created_at", table_name="orchestration_turns")
    op.drop_index("ix_orchestration_turns_conversation_id", table_name="orchestration_turns")
    op.drop_table("orchestration_turns")
