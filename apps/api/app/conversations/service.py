import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_audit_event
from app.conversations import repository, state_machine
from app.conversations.models import Conversation
from app.conversations.schemas import ConversationCreateRequest, ConversationUpdateRequest
from app.customers.service import get_customer_or_404
from app.errors import NotFoundError


async def create_conversation(
    db: AsyncSession, *, tenant_id: uuid.UUID, body: ConversationCreateRequest, actor_user_id: uuid.UUID | None
) -> Conversation:
    await get_customer_or_404(db, tenant_id, body.customer_id)

    conversation = Conversation(
        tenant_id=tenant_id,
        customer_id=body.customer_id,
        channel=body.channel,
        priority=body.priority,
        started_at=datetime.now(UTC),
        conversation_metadata=body.conversation_metadata,
    )
    db.add(conversation)
    await db.flush()

    await record_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action="conversation.created",
        resource_type="conversation",
        resource_id=str(conversation.id),
        metadata={"channel": body.channel},
    )
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def get_conversation_or_404(db: AsyncSession, tenant_id: uuid.UUID, conversation_id: uuid.UUID) -> Conversation:
    conversation = await repository.get_conversation(db, tenant_id, conversation_id)
    if conversation is None:
        raise NotFoundError("Conversation not found")
    return conversation


async def update_conversation(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    conversation_id: uuid.UUID,
    body: ConversationUpdateRequest,
    actor_user_id: uuid.UUID | None,
) -> Conversation:
    conversation = await get_conversation_or_404(db, tenant_id, conversation_id)

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(conversation, field, value)

    await record_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action="conversation.updated",
        resource_type="conversation",
        resource_id=str(conversation.id),
        metadata={"fields": list(updates.keys())},
    )
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def assign_conversation(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    conversation_id: uuid.UUID,
    agent_user_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
) -> Conversation:
    conversation = await get_conversation_or_404(db, tenant_id, conversation_id)
    conversation.assigned_agent_id = agent_user_id
    if conversation.status == "open":
        conversation.status = "waiting_for_staff"

    await record_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action="conversation.assigned",
        resource_type="conversation",
        resource_id=str(conversation.id),
        metadata={"agent_user_id": str(agent_user_id)},
    )
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def change_status(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    conversation_id: uuid.UUID,
    new_status: str,
    actor_user_id: uuid.UUID | None,
) -> Conversation:
    conversation = await get_conversation_or_404(db, tenant_id, conversation_id)
    old_status = conversation.status
    conversation.status = new_status

    if new_status == "ai_handling":
        conversation.ai_active, conversation.human_active = True, False
    elif new_status == "human_handling":
        conversation.ai_active, conversation.human_active = False, True
    elif new_status == "closed":
        conversation.closed_at = datetime.now(UTC)

    await record_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action="conversation.status_changed",
        resource_type="conversation",
        resource_id=str(conversation.id),
        metadata={"old_status": old_status, "new_status": new_status},
    )
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def close_conversation(
    db: AsyncSession, *, tenant_id: uuid.UUID, conversation_id: uuid.UUID, actor_user_id: uuid.UUID | None
) -> Conversation:
    return await change_status(
        db, tenant_id=tenant_id, conversation_id=conversation_id, new_status="closed", actor_user_id=actor_user_id
    )


async def change_dialogue_state(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    conversation_id: uuid.UUID,
    new_state: str,
    changed_by: str,
    metadata: dict | None,
    actor_user_id: uuid.UUID | None,
) -> Conversation:
    conversation = await get_conversation_or_404(db, tenant_id, conversation_id)
    await state_machine.transition_state(
        db, conversation=conversation, to_state=new_state, changed_by=changed_by, metadata=metadata
    )

    await record_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action="conversation.state_changed",
        resource_type="conversation",
        resource_id=str(conversation.id),
        metadata={"to_state": new_state, "changed_by": changed_by},
    )
    await db.commit()
    await db.refresh(conversation)
    return conversation
