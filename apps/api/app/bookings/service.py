"""Phase 7 room-booking business logic. `submit_booking_enquiry` is the one
entry point the AI's create_room_booking tool calls (app.orchestration.
tools.handlers) — it never raises for a guest-facing validation problem,
it returns a structured {"created": False, "reason": ...} dict instead, so
the tool handler can hand that straight back to the LLM as tool output and
let the AI explain the issue to the guest in its own words (an uncaught
exception here would instead fall into the pipeline's generic
"tool failed" apology, discarding exactly the detail the guest needs).
Staff-side actions (confirm/reject/update) are plain service functions that
raise app.errors.AppError subclasses like every other domain, since those
run behind a normal FastAPI request, not an LLM turn.
"""

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.bookings import repository
from app.bookings.models import RoomBooking, RoomType
from app.bookings.sms import send_booking_confirmation_sms
from app.config import get_settings
from app.errors import NotFoundError, ValidationErrorApp
from app.logging import get_logger
from app.notifications.service import notify

logger = get_logger(__name__)

_PHONE_DIGITS_RE = re.compile(r"\d")


@dataclass
class BookingAttemptResult:
    created: bool
    booking_id: uuid.UUID | None = None
    status: str | None = None
    reasons: list[str] = field(default_factory=list)


def _parse_date(value: str | date) -> date | None:
    if isinstance(value, date):
        return value
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


def _validate_phone(phone: str) -> bool:
    digits = _PHONE_DIGITS_RE.findall(phone)
    return 7 <= len(digits) <= 15


async def submit_booking_enquiry(
    db: AsyncSession,
    *,
    conversation_id: uuid.UUID,
    customer_id: uuid.UUID,
    check_in_date: str,
    check_out_date: str,
    num_guests: int | str,
    room_type: str,
    guest_name: str,
    guest_phone: str,
    breakfast_included: bool | None = None,
    special_preferences: str | None = None,
) -> BookingAttemptResult:
    reasons: list[str] = []
    settings = get_settings()
    today = date.today()

    parsed_check_in = _parse_date(check_in_date) if check_in_date else None
    parsed_check_out = _parse_date(check_out_date) if check_out_date else None

    if not guest_name or not guest_name.strip():
        reasons.append("Guest name is missing.")
    if not guest_phone or not _validate_phone(guest_phone):
        reasons.append("Guest phone number looks invalid — ask for a valid contact number.")
    if parsed_check_in is None:
        reasons.append(f"Check-in date '{check_in_date}' isn't a recognizable date (expected YYYY-MM-DD).")
    if parsed_check_out is None:
        reasons.append(f"Check-out date '{check_out_date}' isn't a recognizable date (expected YYYY-MM-DD).")

    try:
        guests_int = int(num_guests)
        if guests_int < 1:
            reasons.append("Number of guests must be at least 1.")
    except (TypeError, ValueError):
        guests_int = None
        reasons.append(f"Number of guests '{num_guests}' isn't a valid number.")

    room = await repository.find_room_type_by_name_or_slug(db, room_type) if room_type else None
    if room is None:
        reasons.append(f"'{room_type}' doesn't match any current room category — ask the guest to pick a listed one.")

    if parsed_check_in and parsed_check_out:
        if parsed_check_in < today:
            reasons.append("Check-in date is in the past.")
        if parsed_check_out <= parsed_check_in:
            reasons.append("Check-out date must be after check-in date.")
        max_date = today + timedelta(days=settings.booking_max_advance_days)
        if parsed_check_in > max_date:
            reasons.append(
                f"Check-in date is more than {settings.booking_max_advance_days} days out — "
                f"we can only take bookings up to {max_date.isoformat()} for now."
            )

    if room is not None and guests_int is not None and guests_int > room.max_occupancy:
        reasons.append(f"{room.name} sleeps a maximum of {room.max_occupancy} guests.")

    if reasons:
        return BookingAttemptResult(created=False, reasons=reasons)

    overlapping = await repository.count_overlapping_bookings(
        db, room_type_id=room.id, check_in_date=parsed_check_in, check_out_date=parsed_check_out
    )
    if overlapping >= room.total_inventory:
        return BookingAttemptResult(
            created=False,
            reasons=[f"No {room.name} rooms are available for those dates — every unit is already held."],
        )

    booking = RoomBooking(
        conversation_id=conversation_id,
        customer_id=customer_id,
        room_type_id=room.id,
        check_in_date=parsed_check_in,
        check_out_date=parsed_check_out,
        num_guests=guests_int,
        breakfast_included=breakfast_included if breakfast_included is not None else room.breakfast_included_default,
        guest_name=guest_name.strip(),
        guest_phone=guest_phone.strip(),
        special_preferences=special_preferences,
        status="pending_review",
    )
    booking = await repository.create_room_booking(db, booking=booking)
    await db.commit()
    await db.refresh(booking)

    await notify(
        db,
        notification_type="room_booking_received",
        title="New room booking to review",
        body=f"{room.name}, {parsed_check_in.isoformat()} to {parsed_check_out.isoformat()} — {guest_name.strip()}",
        resource_type="room_booking",
        resource_id=str(booking.id),
    )

    return BookingAttemptResult(created=True, booking_id=booking.id, status=booking.status)


async def check_availability(
    db: AsyncSession, *, room_type: str, check_in_date: str, check_out_date: str
) -> dict:
    parsed_check_in = _parse_date(check_in_date)
    parsed_check_out = _parse_date(check_out_date)
    if parsed_check_in is None or parsed_check_out is None:
        return {"available": False, "reason": "Could not parse the given dates."}

    room = await repository.find_room_type_by_name_or_slug(db, room_type)
    if room is None:
        return {"available": False, "reason": f"'{room_type}' doesn't match any current room category."}

    if parsed_check_out <= parsed_check_in:
        return {"available": False, "reason": "Check-out date must be after check-in date."}

    settings = get_settings()
    max_date = date.today() + timedelta(days=settings.booking_max_advance_days)
    if parsed_check_in > max_date:
        return {
            "available": False,
            "reason": (
                f"That date is more than {settings.booking_max_advance_days} days out — "
                f"we can only confirm availability up to {max_date.isoformat()} for now."
            ),
        }

    overlapping = await repository.count_overlapping_bookings(
        db, room_type_id=room.id, check_in_date=parsed_check_in, check_out_date=parsed_check_out
    )
    remaining = room.total_inventory - overlapping
    return {
        "available": remaining > 0,
        "room_type": room.name,
        "remaining_units": max(remaining, 0),
        "max_occupancy": room.max_occupancy,
        "breakfast_included_default": room.breakfast_included_default,
    }


async def get_booking_or_404(db: AsyncSession, booking_id: uuid.UUID) -> RoomBooking:
    booking = await repository.get_room_booking(db, booking_id)
    if booking is None:
        raise NotFoundError("Room booking not found")
    return booking


async def update_booking_details(
    db: AsyncSession, *, booking_id: uuid.UUID, updates: dict
) -> RoomBooking:
    booking = await get_booking_or_404(db, booking_id)
    if booking.status != "pending_review":
        raise ValidationErrorApp("Only a pending_review booking can be edited")

    for field_name in (
        "guest_name",
        "guest_phone",
        "check_in_date",
        "check_out_date",
        "num_guests",
        "breakfast_included",
        "special_preferences",
        "staff_notes",
    ):
        if field_name in updates and updates[field_name] is not None:
            setattr(booking, field_name, updates[field_name])

    if booking.check_out_date <= booking.check_in_date:
        raise ValidationErrorApp("Check-out date must be after check-in date")

    await db.commit()
    await db.refresh(booking)
    return booking


async def confirm_booking(db: AsyncSession, *, booking_id: uuid.UUID, actor_user_id: uuid.UUID) -> RoomBooking:
    booking = await get_booking_or_404(db, booking_id)
    if booking.status != "pending_review":
        raise ValidationErrorApp(f"Booking is '{booking.status}', not pending_review — nothing to confirm")

    room = await repository.get_room_type(db, booking.room_type_id)

    booking.status = "confirmed"
    booking.confirmed_by_user_id = actor_user_id
    booking.confirmed_at = datetime.now(UTC)

    sms_result = send_booking_confirmation_sms(
        guest_phone=booking.guest_phone,
        guest_name=booking.guest_name,
        room_type_name=room.name if room else "your room",
        check_in_date=booking.check_in_date.isoformat(),
        check_out_date=booking.check_out_date.isoformat(),
    )
    booking.confirmation_sms_status = sms_result.status
    booking.confirmation_sms_error = sms_result.error

    await db.commit()
    await db.refresh(booking)
    return booking


async def reject_booking(
    db: AsyncSession, *, booking_id: uuid.UUID, staff_notes: str | None, actor_user_id: uuid.UUID
) -> RoomBooking:
    booking = await get_booking_or_404(db, booking_id)
    if booking.status != "pending_review":
        raise ValidationErrorApp(f"Booking is '{booking.status}', not pending_review — nothing to reject")

    booking.status = "rejected"
    booking.confirmed_by_user_id = actor_user_id
    booking.confirmed_at = datetime.now(UTC)
    if staff_notes:
        booking.staff_notes = staff_notes

    await db.commit()
    await db.refresh(booking)
    return booking


async def list_room_types(db: AsyncSession) -> list[RoomType]:
    return await repository.list_room_types(db)
