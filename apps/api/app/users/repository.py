import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.users.models import User


async def get_user(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await db.get(User, user_id)


async def list_users(
    db: AsyncSession,
    *,
    status: str | None = None,
    search: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[User], int]:
    query = select(User)
    count_query = select(func.count()).select_from(User)

    conditions = []
    if status:
        conditions.append(User.status == status)
    if search:
        pattern = f"%{search}%"
        conditions.append(or_(User.full_name.ilike(pattern), User.email.ilike(pattern)))

    for condition in conditions:
        query = query.where(condition)
        count_query = count_query.where(condition)

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(query.order_by(User.full_name.asc().nulls_last()).offset(offset).limit(limit))
    return list(result.scalars().all()), total
