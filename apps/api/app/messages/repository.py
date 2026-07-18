import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.messages.models import Message


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
