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
from app.resort.service import resolve_local_today

logger = get_logger(__name__)

_PHONE_DIGITS_RE = re.compile(r"\d")


@dataclass
class BookingAttemptResult:
    created: bool
    booking_ids: list[uuid.UUID] = field(default_factory=list)
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
    num_rooms: int | str | None = None,
    breakfast_included: bool | None = None,
    special_preferences: str | None = None,
) -> BookingAttemptResult:
    reasons: list[str] = []
    settings = get_settings()
    today = await resolve_local_today(db)

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

    try:
        rooms_int = int(num_rooms) if num_rooms not in (None, "") else 1
        if rooms_int < 1:
            reasons.append("Number of rooms must be at least 1.")
    except (TypeError, ValueError):
        rooms_int = None
        reasons.append(f"Number of rooms '{num_rooms}' isn't a valid number.")

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

    # Occupancy is PER ROOM — a party larger than one room's max_occupancy
    # isn't rejected outright, it's checked against max_occupancy * num_rooms
    # instead (e.g. 4 adults across 2 Honeymoon Pool Villas, max_occupancy 2
    # each, fits fine split 2-and-2 — see the 2026-07-24 incident where the
    # AI wrongly refused exactly this because num_rooms didn't exist yet).
    if room is not None and guests_int is not None and rooms_int is not None:
        if guests_int > room.max_occupancy * rooms_int:
            reasons.append(
                f"{room.name} sleeps a maximum of {room.max_occupancy} guests per room — "
                f"{rooms_int} room(s) can't fit {guests_int} guests. Offer more rooms or a larger room type."
            )

    if reasons:
        return BookingAttemptResult(created=False, reasons=reasons)

    # Locks the room_type row for the rest of this transaction — closes the
    # check-then-insert race where two guests booking the last unit(s)
    # simultaneously could otherwise both pass the count check below before
    # either commits (see repository.lock_room_type_for_booking's docstring).
    await repository.lock_room_type_for_booking(db, room.id)

    overlapping = await repository.count_overlapping_bookings(
        db, room_type_id=room.id, check_in_date=parsed_check_in, check_out_date=parsed_check_out
    )
    if overlapping + rooms_int > room.total_inventory:
        remaining = max(room.total_inventory - overlapping, 0)
        return BookingAttemptResult(
            created=False,
            reasons=[
                f"Only {remaining} {room.name} room(s) are available for those dates — "
                f"{rooms_int} were requested."
            ],
        )

    # Split guests as evenly as possible across the requested rooms (e.g.
    # 4 guests / 2 rooms -> 2 and 2; 5 / 2 -> 3 and 2) — each room still
    # respects its own max_occupancy, already validated above.
    base_guests = guests_int // rooms_int
    remainder = guests_int % rooms_int

    booking_ids: list[uuid.UUID] = []
    for room_index in range(rooms_int):
        room_guests = base_guests + (1 if room_index < remainder else 0)
        note = special_preferences or ""
        if rooms_int > 1:
            group_note = f"Room {room_index + 1} of {rooms_int}, booked together for one party of {guests_int}."
            note = f"{group_note} {note}".strip()

        booking = RoomBooking(
            conversation_id=conversation_id,
            customer_id=customer_id,
            room_type_id=room.id,
            check_in_date=parsed_check_in,
            check_out_date=parsed_check_out,
            num_guests=room_guests,
            breakfast_included=(
                breakfast_included if breakfast_included is not None else room.breakfast_included_default
            ),
            guest_name=guest_name.strip(),
            guest_phone=guest_phone.strip(),
            special_preferences=note or None,
            status="pending_review",
        )
        booking = await repository.create_room_booking(db, booking=booking)
        booking_ids.append(booking.id)

    await db.commit()

    body = f"{room.name}, {parsed_check_in.isoformat()} to {parsed_check_out.isoformat()} — {guest_name.strip()}"
    if rooms_int > 1:
        body = f"{rooms_int}x {body}"
    await notify(
        db,
        notification_type="room_booking_received",
        title="New room booking to review",
        body=body,
        resource_type="room_booking",
        resource_id=str(booking_ids[0]),
    )

    return BookingAttemptResult(created=True, booking_ids=booking_ids, status="pending_review")


async def check_availability(
    db: AsyncSession, *, room_type: str, check_in_date: str, check_out_date: str, num_rooms: int | str | None = None
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

    try:
        rooms_int = int(num_rooms) if num_rooms not in (None, "") else 1
        if rooms_int < 1:
            rooms_int = 1
    except (TypeError, ValueError):
        rooms_int = 1

    settings = get_settings()
    max_date = await resolve_local_today(db) + timedelta(days=settings.booking_max_advance_days)
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
    remaining = max(room.total_inventory - overlapping, 0)
    return {
        "available": remaining >= rooms_int,
        "room_type": room.name,
        "rooms_requested": rooms_int,
        "remaining_units": remaining,
        "max_occupancy_per_room": room.max_occupancy,
        "max_total_guests_for_requested_rooms": room.max_occupancy * rooms_int,
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

    if "num_guests" in updates and updates["num_guests"] is not None:
        room = await repository.get_room_type(db, booking.room_type_id)
        if room is not None and booking.num_guests > room.max_occupancy:
            raise ValidationErrorApp(
                f"{room.name} sleeps a maximum of {room.max_occupancy} guests per room — "
                f"{booking.num_guests} doesn't fit in this one booking row."
            )

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
