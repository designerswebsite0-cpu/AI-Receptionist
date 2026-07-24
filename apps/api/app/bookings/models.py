import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.bookings.constants import BOOKING_STATUSES, SMS_STATUSES
from app.common.models import TimestampMixin, UUIDPrimaryKeyMixin
from app.database import Base


class RoomType(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Real room inventory — seeded (migration 0028) from
    apps/website/src/data/rooms.ts, the resort's actual published room
    catalogue with real per-category counts. `total_inventory` is the hard
    cap availability-checking counts against (app.bookings.repository.
    count_overlapping_bookings); rates are informational for staff/dashboard
    display only — the AI still quotes prices from RETRIEVED_KNOWLEDGE per
    the existing pricing rules, never from this table, to keep one source
    of truth for guest-facing figures."""

    __tablename__ = "room_types"

    slug: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    total_inventory: Mapped[int] = mapped_column(Integer, nullable=False)
    max_occupancy: Mapped[int] = mapped_column(Integer, nullable=False)
    adults_allowed: Mapped[int] = mapped_column(Integer, nullable=False)
    children_allowed: Mapped[int] = mapped_column(Integer, nullable=False)
    breakfast_included_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    low_season_rate: Mapped[int] = mapped_column(Numeric(10, 2), nullable=False)
    high_season_rate: Mapped[int] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class RoomBooking(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A guest-submitted room booking request — never auto-confirmed. Every
    row starts 'pending_review'; only a staff member acting through
    app.bookings.service.confirm_booking (dashboard Confirm action) can move
    it to 'confirmed', which is the point an SMS goes to guest_phone. This
    mirrors the same 'safe enquiry, not a fake completed operation'
    guarantee as app.orchestration.models.ServiceRequest, just in its own
    table per the explicit 2026-07-24 brief."""

    __tablename__ = "room_bookings"

    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    room_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("room_types.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    check_in_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    check_out_date: Mapped[date] = mapped_column(Date, nullable=False)
    num_guests: Mapped[int] = mapped_column(Integer, nullable=False)
    breakfast_included: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    guest_name: Mapped[str] = mapped_column(String(200), nullable=False)
    guest_phone: Mapped[str] = mapped_column(String(30), nullable=False)
    special_preferences: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending_review", index=True)
    staff_notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    confirmed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmation_sms_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    confirmation_sms_error: Mapped[str | None] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        CheckConstraint(f"status IN {BOOKING_STATUSES}", name="ck_room_bookings_status"),
        CheckConstraint(
            f"confirmation_sms_status IS NULL OR confirmation_sms_status IN {SMS_STATUSES}",
            name="ck_room_bookings_sms_status",
        ),
        CheckConstraint("check_out_date > check_in_date", name="ck_room_bookings_dates"),
    )
