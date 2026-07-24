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


async def find_room_type_by_name_or_slug(db: AsyncSession, text: str) -> RoomType | None:
    """Best-effort match against what the guest/AI actually said (e.g.
    'garden deluxe', 'Garden Deluxe Room', 'garden-deluxe-room') — the AI
    doesn't know internal slugs, so this tolerates a case-insensitive
    partial match on either the slug or the display name rather than
    requiring an exact key."""
    normalized = text.strip().lower()
    query = select(RoomType).where(
        RoomType.is_active.is_(True),
        or_(
            func.lower(RoomType.slug) == normalized,
            func.lower(RoomType.name) == normalized,
            func.lower(RoomType.slug).contains(normalized.replace(" ", "-")),
            func.lower(RoomType.name).contains(normalized),
        ),
    )
    result = await db.execute(query.limit(1))
    return result.scalars().first()


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
