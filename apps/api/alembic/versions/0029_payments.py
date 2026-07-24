"""Phase 7: payments (placeholder — no gateway account yet)

Revision ID: 0029
Revises: 0028
Create Date: 2026-07-24

Deliberately a placeholder per the 2026-07-24 brief: no gateway credentials
exist yet, so every row here either records money staff already physically
collected (cash/card_on_arrival/bank_transfer -> immediately 'paid') or logs
a guest's intent to pay online before any gateway exists ('online_pending',
which can only be created, never marked paid, until a real integration is
added — see app.payments.service's module docstring for the exact seam).
RLS follows the established single-resort pattern (0009/0019/.../0028).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_AUTHENTICATED = "auth.uid() IS NOT NULL"


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "room_booking_id", pg.UUID(as_uuid=True), sa.ForeignKey("room_bookings.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "customer_id", pg.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "conversation_id", pg.UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("provider", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("provider_reference", sa.String(200), nullable=True),
        sa.Column("staff_notes", sa.String(2000), nullable=True),
        sa.Column(
            "recorded_by_user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "method IN ('cash', 'card_on_arrival', 'bank_transfer', 'online_pending')", name="ck_payments_method"
        ),
        sa.CheckConstraint("status IN ('pending', 'paid', 'failed', 'refunded')", name="ck_payments_status"),
    )
    op.create_index("ix_payments_room_booking_id", "payments", ["room_booking_id"])
    op.create_index("ix_payments_customer_id", "payments", ["customer_id"])
    op.create_index("ix_payments_status", "payments", ["status"])

    op.execute("ALTER TABLE payments ENABLE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY payments_select ON payments FOR SELECT USING (" + _AUTHENTICATED + ")")
    op.execute(
        "CREATE POLICY payments_modify ON payments FOR ALL "
        "USING (" + _AUTHENTICATED + ") WITH CHECK (" + _AUTHENTICATED + ")"
    )

    op.execute("ALTER TABLE notifications DROP CONSTRAINT ck_notifications_type")
    op.execute(
        "ALTER TABLE notifications ADD CONSTRAINT ck_notifications_type CHECK ("
        "notification_type IN ('handoff_required', 'booking_enquiry_received', "
        "'knowledge_ingestion_failed', 'feedback_received', 'room_booking_received', "
        "'payment_enquiry_received'))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE notifications DROP CONSTRAINT ck_notifications_type")
    op.execute(
        "ALTER TABLE notifications ADD CONSTRAINT ck_notifications_type CHECK ("
        "notification_type IN ('handoff_required', 'booking_enquiry_received', "
        "'knowledge_ingestion_failed', 'feedback_received', 'room_booking_received'))"
    )

    op.execute("DROP POLICY IF EXISTS payments_modify ON payments")
    op.execute("DROP POLICY IF EXISTS payments_select ON payments")
    op.drop_index("ix_payments_status", table_name="payments")
    op.drop_index("ix_payments_customer_id", table_name="payments")
    op.drop_index("ix_payments_room_booking_id", table_name="payments")
    op.drop_table("payments")
