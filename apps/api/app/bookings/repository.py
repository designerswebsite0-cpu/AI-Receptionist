import uuid
from datetime import date

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bookings.constants import ACTIVE_BOOKING_STATUSES
from app.bookings.models import RoomBooking, RoomType


async def list_room_types(db: AsyncSession, *, active_only: bool = True) -> list[RoomType]:
    query = select(RoomType)
    if active_only:
        query = query.where(RoomType.is_active.is_(True))
    result = await db.execute(query.order_by(RoomType.low_season_rate))
    return list(result.scalars().all())


async def get_room_type(db: AsyncSession, room_type_id: uuid.UUID) -> RoomType | None:
    return await db.get(RoomType, room_type_id)


async def lock_room_type_for_booking(db: AsyncSession, room_type_id: uuid.UUID) -> RoomType | None:
    """SELECT ... FOR UPDATE on the room_type row — serializes concurrent
    booking attempts for the SAME room type so two guests racing for the
    last unit(s) can't both pass the availability check before either
    commits. Without this, app.bookings.service.submit_booking_enquiry's
    check-then-insert is a classic TOCTOU race: two simultaneous requests
    each read the same "1 room left" count, both insert, and the resort
    ends up double-booked. Must be called inside the same transaction that
    goes on to count overlapping bookings and insert — the lock is held
    until that transaction commits or rolls back."""
    result = await db.execute(select(RoomType).where(RoomType.id == room_type_id).with_for_update())
    return result.scalars().first()


async def find_room_type_by_name_or_slug(db: AsyncSession, text: str) -> RoomType | None:
    """Best-effort match against what the guest/AI actually said (e.g.
    'garden deluxe', 'Garden Deluxe Room', 'garden-deluxe-room') — the AI
    doesn't know internal slugs, so this tolerates a case-insensitive
    partial match on either the slug or the display name rather than
    requiring an exact key.

    Exact matches are always tried first and returned immediately — only
    falling through to a fuzzy `contains` match when nothing matches
    exactly, and even then the result is ordered deterministically (by
    name length, shortest/most-specific first). Without this, a query like
    'pool villa' — a genuine substring of BOTH "Honeymoon Pool Villa" and
    "Grand Two-Bedroom Pool Villa" — would silently resolve to whichever
    row Postgres happened to return first, i.e. a real risk of quietly
    booking the guest into the wrong room type (see the 2026-07-24 audit)."""
    normalized = text.strip().lower()

    exact_query = select(RoomType).where(
        RoomType.is_active.is_(True),
        or_(func.lower(RoomType.slug) == normalized, func.lower(RoomType.name) == normalized),
    )
    exact_result = await db.execute(exact_query.limit(1))
    exact_match = exact_result.scalars().first()
    if exact_match is not None:
        return exact_match

    fuzzy_query = (
        select(RoomType)
        .where(
            RoomType.is_active.is_(True),
            or_(
                func.lower(RoomType.slug).contains(normalized.replace(" ", "-")),
                func.lower(RoomType.name).contains(normalized),
            ),
        )
        .order_by(func.length(RoomType.name))
    )
    fuzzy_result = await db.execute(fuzzy_query.limit(1))
    return fuzzy_result.scalars().first()


async def count_overlapping_bookings(
    db: AsyncSession, *, room_type_id: uuid.UUID, check_in_date: date, check_out_date: date
) -> int:
    """Two stays overlap unless one ends on/before the other starts —
    standard half-open interval overlap check. Only pending_review/confirmed
    rows hold a room against inventory (see constants.ACTIVE_BOOKING_STATUSES)."""
    query = select(func.count()).select_from(RoomBooking).where(
        RoomBooking.room_type_id == room_type_id,
        RoomBooking.status.in_(ACTIVE_BOOKING_STATUSES),
        and_(
            RoomBooking.check_in_date < check_out_date,
            RoomBooking.check_out_date > check_in_date,
        ),
    )
    return (await db.execute(query)).scalar_one()


async def create_room_booking(db: AsyncSession, *, booking: RoomBooking) -> RoomBooking:
    db.add(booking)
    await db.flush()
    return booking


async def get_room_booking(db: AsyncSession, booking_id: uuid.UUID) -> RoomBooking | None:
    return await db.get(RoomBooking, booking_id)


async def list_room_bookings(
    db: AsyncSession, *, status: str | None = None, offset: int = 0, limit: int = 50
) -> tuple[list[RoomBooking], int]:
    query = select(RoomBooking)
    count_query = select(func.count()).select_from(RoomBooking)
    if status:
        query = query.where(RoomBooking.status == status)
        count_query = count_query.where(RoomBooking.status == status)

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(query.order_by(RoomBooking.created_at.desc()).offset(offset).limit(limit))
    return list(result.scalars().all()), total
