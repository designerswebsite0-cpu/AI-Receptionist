import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.models import Notification


async def create_notification(
    db: AsyncSession,
    *,
    notification_type: str,
    title: str,
    body: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> Notification:
    notification = Notification(
        notification_type=notification_type,
        title=title,
        body=body,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    db.add(notification)
    await db.flush()
    return notification


async def get_notification(db: AsyncSession, notification_id: uuid.UUID) -> Notification | None:
    return await db.get(Notification, notification_id)


async def list_notifications(
    db: AsyncSession,
    *,
    unread_only: bool = False,
    notification_type: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[Notification], int]:
    query = select(Notification)
    count_query = select(func.count()).select_from(Notification)

    conditions = []
    if unread_only:
        conditions.append(Notification.read_at.is_(None))
    if notification_type:
        conditions.append(Notification.notification_type == notification_type)

    for condition in conditions:
        query = query.where(condition)
        count_query = count_query.where(condition)

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(query.order_by(Notification.created_at.desc()).offset(offset).limit(limit))
    return list(result.scalars().all()), total


async def count_unread(db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count()).select_from(Notification).where(Notification.read_at.is_(None))
    )
    return result.scalar_one()


async def mark_all_read(db: AsyncSession, *, actor_user_id: uuid.UUID | None) -> int:
    result = await db.execute(
        update(Notification)
        .where(Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC), read_by_user_id=actor_user_id)
    )
    return result.rowcount or 0
