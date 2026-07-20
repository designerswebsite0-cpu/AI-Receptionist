"""Phase X Stage 6: notifications

Revision ID: 0026
Revises: 0025
Create Date: 2026-07-20

A resort-wide, shared notification feed (see app/notifications/constants.py
for why there's no per-recipient column). RLS follows the established
single-resort pattern (0009/0019/0023/0024): the backend's service_role
connection is the real authorization gate; `auth.uid() IS NOT NULL` here is
defense-in-depth for any direct Postgres/PostgREST access path.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_AUTHENTICATED = "auth.uid() IS NOT NULL"


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("body", sa.String(2000), nullable=True),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column("resource_id", sa.String(64), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "read_by_user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "notification_type IN ('handoff_required', 'booking_enquiry_received', "
            "'knowledge_ingestion_failed', 'feedback_received')",
            name="ck_notifications_type",
        ),
    )
    op.create_index("ix_notifications_notification_type", "notifications", ["notification_type"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])

    op.execute("ALTER TABLE notifications ENABLE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY notifications_select ON notifications FOR SELECT USING (" + _AUTHENTICATED + ")")
    op.execute(
        "CREATE POLICY notifications_modify ON notifications FOR ALL "
        "USING (" + _AUTHENTICATED + ") WITH CHECK (" + _AUTHENTICATED + ")"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS notifications_modify ON notifications")
    op.execute("DROP POLICY IF EXISTS notifications_select ON notifications")
    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_index("ix_notifications_notification_type", table_name="notifications")
    op.drop_table("notifications")
