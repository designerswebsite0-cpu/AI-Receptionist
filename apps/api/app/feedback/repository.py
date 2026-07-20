import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.feedback.models import CustomerFeedback


async def create_feedback(
    db: AsyncSession,
    *,
    category: str,
    rating: str,
    comment: str | None,
    conversation_id: uuid.UUID | None,
    customer_id: uuid.UUID | None,
    turn_id: uuid.UUID | None,
) -> CustomerFeedback:
    feedback = CustomerFeedback(
        category=category,
        rating=rating,
        comment=comment,
        conversation_id=conversation_id,
        customer_id=customer_id,
        turn_id=turn_id,
    )
    db.add(feedback)
    await db.flush()
    return feedback


async def get_feedback(db: AsyncSession, feedback_id: uuid.UUID) -> CustomerFeedback | None:
    return await db.get(CustomerFeedback, feedback_id)


async def list_feedback(
    db: AsyncSession,
    *,
    category: str | None = None,
    rating: str | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[CustomerFeedback], int]:
    query = select(CustomerFeedback)
    count_query = select(func.count()).select_from(CustomerFeedback)

    conditions = []
    if category:
        conditions.append(CustomerFeedback.category == category)
    if rating:
        conditions.append(CustomerFeedback.rating == rating)
    if status:
        conditions.append(CustomerFeedback.status == status)

    for condition in conditions:
        query = query.where(condition)
        count_query = count_query.where(condition)

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(query.order_by(CustomerFeedback.created_at.desc()).offset(offset).limit(limit))
    return list(result.scalars().all()), total


async def get_stats(db: AsyncSession) -> tuple[int, int, int, dict[str, int]]:
    """Real aggregates only — counts by rating and by category. No
    sentiment scoring or fabricated trend lines (brief: 'no fabricated
    sentiment ML')."""
    rating_rows = (
        await db.execute(select(CustomerFeedback.rating, func.count()).group_by(CustomerFeedback.rating))
    ).all()
    rating_counts = dict(rating_rows)
    up_count = rating_counts.get("up", 0)
    down_count = rating_counts.get("down", 0)

    category_rows = (
        await db.execute(select(CustomerFeedback.category, func.count()).group_by(CustomerFeedback.category))
    ).all()
    by_category = dict(category_rows)

    return up_count, down_count, up_count + down_count, by_category
