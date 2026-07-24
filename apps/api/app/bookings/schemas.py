import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.bookings.models import RoomBooking, RoomType


class RoomTypeOut(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    total_inventory: int
    max_occupancy: int
    adults_allowed: int
    children_allowed: int
    breakfast_included_default: bool
    low_season_rate: float
    high_season_rate: float
    currency: str

    @classmethod
    def from_model(cls, room_type: RoomType) -> "RoomTypeOut":
        return cls(
            id=room_type.id,
            slug=room_type.slug,
            name=room_type.name,
            total_inventory=room_type.total_inventory,
            max_occupancy=room_type.max_occupancy,
            adults_allowed=room_type.adults_allowed,
            children_allowed=room_type.children_allowed,
            breakfast_included_default=room_type.breakfast_included_default,
            low_season_rate=float(room_type.low_season_rate),
            high_season_rate=float(room_type.high_season_rate),
            currency=room_type.currency,
        )


class RoomBookingOut(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID | None
    customer_id: uuid.UUID
    customer_name: str | None = None
    room_type_id: uuid.UUID
    room_type_name: str | None = None
    check_in_date: date
    check_out_date: date
    num_guests: int
    breakfast_included: bool
    guest_name: str
    guest_phone: str
    special_preferences: str | None
    status: str
    staff_notes: str | None
    confirmed_by_user_id: uuid.UUID | None
    confirmed_at: datetime | None
    confirmation_sms_status: str | None
    confirmation_sms_error: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(
        cls, booking: RoomBooking, *, customer_name: str | None = None, room_type_name: str | None = None
    ) -> "RoomBookingOut":
        return cls(
            id=booking.id,
            conversation_id=booking.conversation_id,
            customer_id=booking.customer_id,
            customer_name=customer_name,
            room_type_id=booking.room_type_id,
            room_type_name=room_type_name,
            check_in_date=booking.check_in_date,
            check_out_date=booking.check_out_date,
            num_guests=booking.num_guests,
            breakfast_included=booking.breakfast_included,
            guest_name=booking.guest_name,
            guest_phone=booking.guest_phone,
            special_preferences=booking.special_preferences,
            status=booking.status,
            staff_notes=booking.staff_notes,
            confirmed_by_user_id=booking.confirmed_by_user_id,
            confirmed_at=booking.confirmed_at,
            confirmation_sms_status=booking.confirmation_sms_status,
            confirmation_sms_error=booking.confirmation_sms_error,
            created_at=booking.created_at,
            updated_at=booking.updated_at,
        )


class RoomBookingStaffUpdateRequest(BaseModel):
    """Lets staff correct guest-supplied data before confirming — the
    'staff must review and double check everything' requirement — without a
    separate edit endpoint. Confirm/reject are their own actions (below),
    not folded into this generic PATCH, since they carry side effects
    (SMS, timestamps) a plain field edit must never trigger."""

    guest_name: str | None = Field(default=None, min_length=1, max_length=200)
    guest_phone: str | None = Field(default=None, min_length=5, max_length=30)
    check_in_date: date | None = None
    check_out_date: date | None = None
    num_guests: int | None = Field(default=None, ge=1)
    breakfast_included: bool | None = None
    special_preferences: str | None = Field(default=None, max_length=2000)
    staff_notes: str | None = Field(default=None, max_length=2000)


class RoomBookingRejectRequest(BaseModel):
    staff_notes: str | None = Field(default=None, max_length=2000)
