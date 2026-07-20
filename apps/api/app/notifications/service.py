"""Notifications (Phase X Stage 6): a thin, resort-wide shared feed emitted
from real event points already in the codebase — never a synthetic/demo
event. See the call sites in app.orchestration.pipeline (handoff),
app.orchestration.tools.handlers (new booking enquiry), and
app.knowledge.service (ingestion failure).
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import NotFoundError
from app.notifications import repository
from app.notifications.models import Notification


async def notify(
    db: AsyncSession,
    *,
    notification_type: str,
    title: str,
    body: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> Notification:
    """Self-committing (unlike app.audit.service.record_audit_event) so a
    notification is never silently lost if a call site forgets to commit
    afterward — every emission point above is a fire-and-forget side
    effect of a larger operation, not something worth coupling to that
    operation's own transaction boundary."""
    notification = await repository.create_notification(
        db,
        notification_type=notification_type,
        title=title,
        body=body,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    await db.commit()
    await db.refresh(notification)
    return notification


async def get_notification_or_404(db: AsyncSession, notification_id: uuid.UUID) -> Notification:
    notification = await repository.get_notification(db, notification_id)
    if notification is None:
        raise NotFoundError("Notification not found")
    return notification


async def mark_notification_read(
    db: AsyncSession, *, notification_id: uuid.UUID, actor_user_id: uuid.UUID | None
) -> Notification:
    notification = await get_notification_or_404(db, notification_id)
    if notification.read_at is None:
        notification.read_at = datetime.now(UTC)
        notification.read_by_user_id = actor_user_id
        await db.commit()
        await db.refresh(notification)
    return notification


async def mark_all_notifications_read(db: AsyncSession, *, actor_user_id: uuid.UUID | None) -> int:
    count = await repository.mark_all_read(db, actor_user_id=actor_user_id)
    await db.commit()
    return count
