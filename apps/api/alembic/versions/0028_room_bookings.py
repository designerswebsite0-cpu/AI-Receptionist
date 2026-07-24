"""Phase 7: room booking system

Revision ID: 0028
Revises: 0027
Create Date: 2026-07-24

A dedicated room_types + room_bookings pair of tables — the real Phase 7
"business operations: booking rooms" system, distinct from the old Stage 5
booking_enquiry triage over the generic service_requests/ServiceRequest
table (that table still serves dining/spa/activity/transfer/complaint
enquiries; room bookings now live here instead). room_types is seeded from
apps/website/src/data/rooms.ts, the resort's real published room catalogue
(6 categories with real per-category inventory counts and rates) — this is
reference/inventory data, not demo data. RLS follows the established
single-resort pattern (0009/0019/0023/0024/0026/0027).
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_AUTHENTICATED = "auth.uid() IS NOT NULL"

# Real room catalogue — mirrors apps/website/src/data/rooms.ts exactly
# (id/slug/name/inventory/maxOccupancy/adultsAllowed/childrenAllowed/
# breakfastIncluded/rates), the resort's actual published data, not
# invented placeholder rooms.
_ROOM_TYPES = [
    {
        "slug": "garden-deluxe-room", "name": "Garden Deluxe Room", "total_inventory": 24,
        "max_occupancy": 3, "adults_allowed": 2, "children_allowed": 1,
        "low_season_rate": 9500, "high_season_rate": 12500,
    },
    {
        "slug": "valley-view-premium-room", "name": "Valley View Premium Room", "total_inventory": 20,
        "max_occupancy": 4, "adults_allowed": 3, "children_allowed": 2,
        "low_season_rate": 11500, "high_season_rate": 14500,
    },
    {
        "slug": "mountain-panorama-suite", "name": "Mountain Panorama Suite", "total_inventory": 10,
        "max_occupancy": 4, "adults_allowed": 3, "children_allowed": 2,
        "low_season_rate": 16500, "high_season_rate": 21000,
    },
    {
        "slug": "family-courtyard-suite", "name": "Family Courtyard Suite", "total_inventory": 8,
        "max_occupancy": 5, "adults_allowed": 4, "children_allowed": 3,
        "low_season_rate": 19500, "high_season_rate": 24500,
    },
    {
        "slug": "honeymoon-pool-villa", "name": "Honeymoon Pool Villa", "total_inventory": 6,
        "max_occupancy": 2, "adults_allowed": 2, "children_allowed": 0,
        "low_season_rate": 26500, "high_season_rate": 33500,
    },
    {
        "slug": "grand-two-bedroom-pool-villa", "name": "Grand Two-Bedroom Pool Villa", "total_inventory": 4,
        "max_occupancy": 7, "adults_allowed": 6, "children_allowed": 3,
        "low_season_rate": 42000, "high_season_rate": 52000,
    },
]


def upgrade() -> None:
    op.create_table(
        "room_types",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(60), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("total_inventory", sa.Integer(), nullable=False),
        sa.Column("max_occupancy", sa.Integer(), nullable=False),
        sa.Column("adults_allowed", sa.Integer(), nullable=False),
        sa.Column("children_allowed", sa.Integer(), nullable=False),
        sa.Column("breakfast_included_default", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("low_season_rate", sa.Numeric(10, 2), nullable=False),
        sa.Column("high_season_rate", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_room_types_slug", "room_types", ["slug"])

    room_types_table = sa.table(
        "room_types",
        sa.column("id", pg.UUID(as_uuid=True)),
        sa.column("slug", sa.String),
        sa.column("name", sa.String),
        sa.column("total_inventory", sa.Integer),
        sa.column("max_occupancy", sa.Integer),
        sa.column("adults_allowed", sa.Integer),
        sa.column("children_allowed", sa.Integer),
        sa.column("low_season_rate", sa.Numeric),
        sa.column("high_season_rate", sa.Numeric),
    )
    op.bulk_insert(
        room_types_table,
        [{**row, "id": uuid.uuid4()} for row in _ROOM_TYPES],
    )

    op.create_table(
        "room_bookings",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_id", pg.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "customer_id", pg.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "room_type_id", pg.UUID(as_uuid=True), sa.ForeignKey("room_types.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("check_in_date", sa.Date(), nullable=False),
        sa.Column("check_out_date", sa.Date(), nullable=False),
        sa.Column("num_guests", sa.Integer(), nullable=False),
        sa.Column("breakfast_included", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("guest_name", sa.String(200), nullable=False),
        sa.Column("guest_phone", sa.String(30), nullable=False),
        sa.Column("special_preferences", sa.String(2000), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending_review"),
        sa.Column("staff_notes", sa.String(2000), nullable=True),
        sa.Column(
            "confirmed_by_user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmation_sms_status", sa.String(30), nullable=True),
        sa.Column("confirmation_sms_error", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending_review', 'confirmed', 'rejected', 'cancelled')", name="ck_room_bookings_status"
        ),
        sa.CheckConstraint(
            "confirmation_sms_status IS NULL OR confirmation_sms_status IN "
            "('sent', 'failed', 'skipped_not_configured')",
            name="ck_room_bookings_sms_status",
        ),
        sa.CheckConstraint("check_out_date > check_in_date", name="ck_room_bookings_dates"),
    )
    op.create_index("ix_room_bookings_conversation_id", "room_bookings", ["conversation_id"])
    op.create_index("ix_room_bookings_customer_id", "room_bookings", ["customer_id"])
    op.create_index("ix_room_bookings_room_type_id", "room_bookings", ["room_type_id"])
    op.create_index("ix_room_bookings_check_in_date", "room_bookings", ["check_in_date"])
    op.create_index("ix_room_bookings_status", "room_bookings", ["status"])

    for table in ("room_types", "room_bookings"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY {table}_select ON {table} FOR SELECT USING (" + _AUTHENTICATED + ")")
        op.execute(
            f"CREATE POLICY {table}_modify ON {table} FOR ALL "
            "USING (" + _AUTHENTICATED + ") WITH CHECK (" + _AUTHENTICATED + ")"
        )

    # New notification type for staff review queue (room_booking_received) —
    # extends the check constraint 0026 created rather than replacing it.
    op.execute("ALTER TABLE notifications DROP CONSTRAINT ck_notifications_type")
    op.execute(
        "ALTER TABLE notifications ADD CONSTRAINT ck_notifications_type CHECK ("
        "notification_type IN ('handoff_required', 'booking_enquiry_received', "
        "'knowledge_ingestion_failed', 'feedback_received', 'room_booking_received'))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE notifications DROP CONSTRAINT ck_notifications_type")
    op.execute(
        "ALTER TABLE notifications ADD CONSTRAINT ck_notifications_type CHECK ("
        "notification_type IN ('handoff_required', 'booking_enquiry_received', "
        "'knowledge_ingestion_failed', 'feedback_received'))"
    )

    for table in ("room_bookings", "room_types"):
        op.execute(f"DROP POLICY IF EXISTS {table}_modify ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_select ON {table}")

    op.drop_index("ix_room_bookings_status", table_name="room_bookings")
    op.drop_index("ix_room_bookings_check_in_date", table_name="room_bookings")
    op.drop_index("ix_room_bookings_room_type_id", table_name="room_bookings")
    op.drop_index("ix_room_bookings_customer_id", table_name="room_bookings")
    op.drop_index("ix_room_bookings_conversation_id", table_name="room_bookings")
    op.drop_table("room_bookings")

    op.drop_index("ix_room_types_slug", table_name="room_types")
    op.drop_table("room_types")
