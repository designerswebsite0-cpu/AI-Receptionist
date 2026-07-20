"""Notifications (Phase X Stage 6) tests — the resort-wide shared feed.
Requires a reachable Postgres (see conftest.db_engine); skips cleanly when
none is available.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import NotFoundError
from app.notifications import repository, service
from app.users.models import User


async def _make_staff_user(db: AsyncSession) -> User:
    user = User(id=uuid.uuid4(), email=f"staff-{uuid.uuid4().hex[:8]}@example.com")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.mark.asyncio
async def test_notify_creates_an_unread_notification(db_session: AsyncSession):
    notification = await service.notify(
        db_session,
        notification_type="handoff_required",
        title="Guest needs human help",
        resource_type="conversation",
        resource_id=str(uuid.uuid4()),
    )

    assert notification.read_at is None
    fetched = await repository.get_notification(db_session, notification.id)
    assert fetched is not None
    assert fetched.title == "Guest needs human help"


@pytest.mark.asyncio
async def test_mark_notification_read_is_idempotent(db_session: AsyncSession):
    notification = await service.notify(
        db_session, notification_type="feedback_received", title="New feedback"
    )
    first_actor = await _make_staff_user(db_session)
    second_actor = await _make_staff_user(db_session)

    first = await service.mark_notification_read(
        db_session, notification_id=notification.id, actor_user_id=first_actor.id
    )
    assert first.read_at is not None
    first_read_at = first.read_at

    second = await service.mark_notification_read(
        db_session, notification_id=notification.id, actor_user_id=second_actor.id
    )
    assert second.read_at == first_read_at  # unchanged — already read, second caller doesn't steal it


@pytest.mark.asyncio
async def test_mark_read_on_unknown_notification_404s(db_session: AsyncSession):
    with pytest.raises(NotFoundError):
        await service.mark_notification_read(db_session, notification_id=uuid.uuid4(), actor_user_id=None)


@pytest.mark.asyncio
async def test_list_notifications_unread_only_filter(db_session: AsyncSession):
    unread = await service.notify(
        db_session, notification_type="booking_enquiry_received", title="Unread one"
    )
    read = await service.notify(
        db_session, notification_type="booking_enquiry_received", title="Read one"
    )
    await service.mark_notification_read(db_session, notification_id=read.id, actor_user_id=None)

    unread_items, _ = await repository.list_notifications(db_session, unread_only=True)
    unread_ids = [n.id for n in unread_items]

    assert unread.id in unread_ids
    assert read.id not in unread_ids


@pytest.mark.asyncio
async def test_mark_all_read_clears_unread_count(db_session: AsyncSession):
    await service.notify(db_session, notification_type="knowledge_ingestion_failed", title="A")
    await service.notify(db_session, notification_type="knowledge_ingestion_failed", title="B")

    before = await repository.count_unread(db_session)
    assert before >= 2

    actor = await _make_staff_user(db_session)
    marked = await service.mark_all_notifications_read(db_session, actor_user_id=actor.id)
    assert marked >= 2

    after = await repository.count_unread(db_session)
    assert after == 0
