"""Phase X Stage 7: customer_feedback

Revision ID: 0027
Revises: 0026
Create Date: 2026-07-20

Structured, queryable feedback rows. webchat's existing
app.webchat.service.submit_feedback() keeps its current audit-log write
(untouched, preserves working behavior) and additionally inserts one row
here so guest thumbs-up/down surfaces as a real dashboard item instead of
only being visible by grepping audit_logs. RLS follows the established
single-resort pattern (0009/0019/0023/0024/0026).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_AUTHENTICATED = "auth.uid() IS NOT NULL"


def upgrade() -> None:
    op.create_table(
        "customer_feedback",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("rating", sa.String(10), nullable=False),
        sa.Column("comment", sa.String(2000), nullable=True),
        sa.Column(
            "conversation_id", pg.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "customer_id", pg.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "turn_id", pg.UUID(as_uuid=True),
            sa.ForeignKey("orchestration_turns.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="new"),
        sa.Column(
            "assigned_agent_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("category IN ('website_chat', 'general')", name="ck_customer_feedback_category"),
        sa.CheckConstraint("rating IN ('up', 'down')", name="ck_customer_feedback_rating"),
        sa.CheckConstraint(
            "status IN ('new', 'reviewed', 'actioned', 'dismissed')", name="ck_customer_feedback_status"
        ),
    )
    op.create_index("ix_customer_feedback_category", "customer_feedback", ["category"])
    op.create_index("ix_customer_feedback_rating", "customer_feedback", ["rating"])
    op.create_index("ix_customer_feedback_conversation_id", "customer_feedback", ["conversation_id"])
    op.create_index("ix_customer_feedback_customer_id", "customer_feedback", ["customer_id"])
    op.create_index("ix_customer_feedback_status", "customer_feedback", ["status"])
    op.create_index("ix_customer_feedback_created_at", "customer_feedback", ["created_at"])

    op.execute("ALTER TABLE customer_feedback ENABLE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY customer_feedback_select ON customer_feedback FOR SELECT USING (" + _AUTHENTICATED + ")")
    op.execute(
        "CREATE POLICY customer_feedback_modify ON customer_feedback FOR ALL "
        "USING (" + _AUTHENTICATED + ") WITH CHECK (" + _AUTHENTICATED + ")"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS customer_feedback_modify ON customer_feedback")
    op.execute("DROP POLICY IF EXISTS customer_feedback_select ON customer_feedback")
    op.drop_index("ix_customer_feedback_created_at", table_name="customer_feedback")
    op.drop_index("ix_customer_feedback_status", table_name="customer_feedback")
    op.drop_index("ix_customer_feedback_customer_id", table_name="customer_feedback")
    op.drop_index("ix_customer_feedback_conversation_id", table_name="customer_feedback")
    op.drop_index("ix_customer_feedback_rating", table_name="customer_feedback")
    op.drop_index("ix_customer_feedback_category", table_name="customer_feedback")
    op.drop_table("customer_feedback")
