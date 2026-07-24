import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.payments.models import Payment


async def create_payment(db: AsyncSession, *, payment: Payment) -> Payment:
    db.add(payment)
    await db.flush()
    return payment


async def get_payment(db: AsyncSession, payment_id: uuid.UUID) -> Payment | None:
    return await db.get(Payment, payment_id)


async def list_payments(
    db: AsyncSession,
    *,
    room_booking_id: uuid.UUID | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[Payment], int]:
    query = select(Payment)
    count_query = select(func.count()).select_from(Payment)
    if room_booking_id:
        query = query.where(Payment.room_booking_id == room_booking_id)
        count_query = count_query.where(Payment.room_booking_id == room_booking_id)
    if status:
        query = query.where(Payment.status == status)
        count_query = count_query.where(Payment.status == status)

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(query.order_by(Payment.created_at.desc()).offset(offset).limit(limit))
    return list(result.scalars().all()), total


async def sum_paid_for_booking(db: AsyncSession, *, room_booking_id: uuid.UUID) -> float:
    result = await db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.room_booking_id == room_booking_id, Payment.status == "paid"
        )
    )
    return float(result.scalar_one())
