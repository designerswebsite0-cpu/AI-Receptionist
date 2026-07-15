import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversations.models import Conversation


async def get_conversation(db: AsyncSession, tenant_id: uuid.UUID, conversation_id: uuid.UUID) -> Conversation | None:
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def search_conversations(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    status: str | None,
    channel: str | None,
    assigned_agent_id: uuid.UUID | None,
    customer_id: uuid.UUID | None,
    offset: int,
    limit: int,
) -> tuple[list[Conversation], int]:
    query = select(Conversation).where(Conversation.tenant_id == tenant_id)
    count_query = select(func.count()).select_from(Conversation).where(Conversation.tenant_id == tenant_id)

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

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(query.order_by(Conversation.started_at.desc()).offset(offset).limit(limit))
    return list(result.scalars().all()), total
