import uuid

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversations.models import Conversation
from app.messages.models import Message

# Kept in sync with app.messages.repository's own definition (same
# question — "does staff still need to look at this?" — asked from two
# different tables' worth of query).
_UNREAD_ELIGIBLE_SENDER_TYPES = ("customer", "ai", "system")


async def get_conversation(db: AsyncSession, conversation_id: uuid.UUID) -> Conversation | None:
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    return result.scalar_one_or_none()


async def search_conversations(
    db: AsyncSession,
    *,
    status: str | None,
    channel: str | None,
    assigned_agent_id: uuid.UUID | None,
    customer_id: uuid.UUID | None,
    priority: str | None = None,
    ai_active: bool | None = None,
    unread: bool | None = None,
    offset: int,
    limit: int,
) -> tuple[list[Conversation], int]:
    query = select(Conversation)
    count_query = select(func.count()).select_from(Conversation)

    if status:
        query = query.where(Conversation.status == status)
        count_query = count_query.where(Conversation.status == status)
    if channel:
        query = query.where(Conversation.channel == channel)
        count_query = count_query.where(Conversation.channel == channel)
    if assigned_agent_id:
        query = query.where(Conversation.assigned_agent_id == assigned_agent_id)
        count_query = count_query.where(Conversation.assigned_agent_id == assigned_agent_id)
    if customer_id:
        query = query.where(Conversation.customer_id == customer_id)
        count_query = count_query.where(Conversation.customer_id == customer_id)
    if priority:
        query = query.where(Conversation.priority == priority)
        count_query = count_query.where(Conversation.priority == priority)
    if ai_active is not None:
        query = query.where(Conversation.ai_active == ai_active)
        count_query = count_query.where(Conversation.ai_active == ai_active)
    if unread is not None:
        has_unread = exists(
            select(1).where(
                Message.conversation_id == Conversation.id,
                Message.read_at.is_(None),
                Message.sender_type.in_(_UNREAD_ELIGIBLE_SENDER_TYPES),
            )
        )
        condition = has_unread if unread else ~has_unread
        query = query.where(condition)
        count_query = count_query.where(condition)

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(query.order_by(Conversation.started_at.desc()).offset(offset).limit(limit))
    return list(result.scalars().all()), total


async def get_conversation_stats_by_customer(
    db: AsyncSession, customer_ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[int, object | None]]:
    """Batched (conversation_count, last_message_at) per customer — used by
    the Customer 360 list (number of conversations, last interaction)
    without an N+1 query per row."""
    if not customer_ids:
        return {}
    result = await db.execute(
        select(Conversation.customer_id, func.count(), func.max(Conversation.last_message_at))
        .where(Conversation.customer_id.in_(customer_ids))
        .group_by(Conversation.customer_id)
    )
    return {row[0]: (row[1], row[2]) for row in result.all()}


async def count_open_conversations_by_agent(db: AsyncSession, agent_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    """Batched count of not-yet-closed conversations per assigned agent —
    used by the Staff Management roster (Phase X Stage 4) to show each
    staff member's current workload without an N+1 query per row."""
    if not agent_ids:
        return {}
    result = await db.execute(
        select(Conversation.assigned_agent_id, func.count())
        .where(Conversation.assigned_agent_id.in_(agent_ids), Conversation.status != "closed")
        .group_by(Conversation.assigned_agent_id)
    )
    return {row[0]: row[1] for row in result.all()}
