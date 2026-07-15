import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversations.models import Conversation, ConversationStateEvent

# The "reusable conversation state engine" the Phase 2 brief asks for. It is
# deliberately permissive — any DIALOGUE_STATE to any other is allowed —
# because validating which transitions make business sense belongs to the
# Phase 4 AI Orchestration Engine (validate_booking_flow-style logic), not
# to this storage/audit layer. What this guarantees: current_state is
# always readable independently of any AI process, and every change is
# durably logged with who/what changed it.


async def transition_state(
    db: AsyncSession,
    *,
    conversation: Conversation,
    to_state: str,
    changed_by: str,
    metadata: dict | None = None,
) -> ConversationStateEvent:
    event = ConversationStateEvent(
        tenant_id=conversation.tenant_id,
        conversation_id=conversation.id,
        from_state=conversation.current_state,
        to_state=to_state,
        changed_by=changed_by,
        event_metadata=metadata or {},
    )
    conversation.current_state = to_state
    db.add(event)
    return event


async def get_state_history(db: AsyncSession, tenant_id: uuid.UUID, conversation_id: uuid.UUID) -> list:
    result = await db.execute(
        select(ConversationStateEvent)
        .where(
            ConversationStateEvent.tenant_id == tenant_id,
            ConversationStateEvent.conversation_id == conversation_id,
        )
        .order_by(ConversationStateEvent.created_at.asc())
    )
    return list(result.scalars().all())
