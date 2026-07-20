import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.messages.models import Message

# Staff-authored replies are never "unread" from the staff inbox's own
# point of view — only what a guest or the AI sent counts toward the
# unread indicator/filter.
_UNREAD_ELIGIBLE_SENDER_TYPES = ("customer", "ai", "system")


async def get_message(db: AsyncSession, message_id: uuid.UUID) -> Message | None:
    result = await db.execute(
        select(Message).options(selectinload(Message.attachments)).where(Message.id == message_id)
    )
    return result.scalar_one_or_none()


async def list_messages(
    db: AsyncSession, conversation_id: uuid.UUID, *, offset: int, limit: int
) -> tuple[list[Message], int]:
    base = select(Message).where(Message.conversation_id == conversation_id)
    total = (
        await db.execute(select(func.count()).select_from(Message).where(Message.conversation_id == conversation_id))
    ).scalar_one()
    result = await db.execute(
        base.options(selectinload(Message.attachments)).order_by(Message.created_at.asc()).offset(offset).limit(limit)
    )
    return list(result.scalars().all()), total


async def list_recent_messages(db: AsyncSession, conversation_id: uuid.UUID, *, limit: int) -> list[Message]:
    """Most recent N messages, returned in chronological order — used by
    app.orchestration.context.assembler to build the conversation-history
    portion of the AI's context. Distinct from list_messages (which is
    offset-paginated from the start, for the dashboard inbox view)."""
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    return list(reversed(result.scalars().all()))


async def find_by_external_id(db: AsyncSession, external_message_id: str) -> Message | None:
    """Idempotency lookup — rules.md §13: retried webhook deliveries must
    not create duplicate messages."""
    result = await db.execute(select(Message).where(Message.external_message_id == external_message_id))
    return result.scalar_one_or_none()


def _unread_filter():
    return (Message.read_at.is_(None)) & (Message.sender_type.in_(_UNREAD_ELIGIBLE_SENDER_TYPES))


async def count_unread(db: AsyncSession, conversation_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Message)
        .where(Message.conversation_id == conversation_id, _unread_filter())
    )
    return result.scalar_one()


async def count_unread_by_conversation(db: AsyncSession, conversation_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    """Batched version of count_unread for a page of conversations (the
    Inbox list) — one query instead of N, per-row unread counts merged
    into the list response."""
    if not conversation_ids:
        return {}
    result = await db.execute(
        select(Message.conversation_id, func.count())
        .where(Message.conversation_id.in_(conversation_ids), _unread_filter())
        .group_by(Message.conversation_id)
    )
    return dict(result.all())


async def mark_all_read(db: AsyncSession, conversation_id: uuid.UUID) -> int:
    """Bulk-marks every currently-unread guest/AI/system message in a
    conversation as read — used when staff opens a thread, and by the
    explicit "mark as read" inbox action. Returns how many rows changed."""
    result = await db.execute(
        update(Message)
        .where(Message.conversation_id == conversation_id, _unread_filter())
        .values(read_at=datetime.now(UTC))
    )
    return result.rowcount or 0


async def mark_latest_unread(db: AsyncSession, conversation_id: uuid.UUID) -> Message | None:
    """The explicit "mark as unread" inbox action — guests/the AI don't
    have a concept of re-marking something unread, so this only ever nulls
    the most recent guest/AI/system message's read_at, simulating "I
    haven't looked at this yet" without inventing a new column."""
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id, Message.sender_type.in_(_UNREAD_ELIGIBLE_SENDER_TYPES))
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    message = result.scalar_one_or_none()
    if message is not None:
        message.read_at = None
    return message
