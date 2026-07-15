import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_audit_event
from app.conversations.service import get_conversation_or_404
from app.errors import ConflictError, NotFoundError
from app.messages import repository
from app.messages.models import Message, MessageAttachment
from app.messages.schemas import MessageCreateRequest


async def send_message(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    conversation_id: uuid.UUID,
    body: MessageCreateRequest,
    actor_user_id: uuid.UUID | None,
) -> Message:
    conversation = await get_conversation_or_404(db, tenant_id, conversation_id)

    if body.external_message_id:
        existing = await repository.find_by_external_id(db, tenant_id, body.external_message_id)
        if existing is not None:
            # Idempotent replay (rules.md §13): return the already-recorded
            # message instead of creating a duplicate.
            return existing

    direction = "inbound" if body.sender_type == "customer" else "outbound"
    message = Message(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        direction=direction,
        sender_type=body.sender_type,
        sender_user_id=actor_user_id if body.sender_type == "human" else None,
        content_type=body.content_type,
        content_text=body.content_text,
        delivery_status="sent" if direction == "outbound" else "delivered",
        external_message_id=body.external_message_id,
        message_metadata=body.message_metadata,
    )
    db.add(message)
    await db.flush()

    for attachment in body.attachments:
        db.add(
            MessageAttachment(
                tenant_id=tenant_id,
                message_id=message.id,
                attachment_type=attachment.attachment_type,
                storage_path=attachment.storage_path,
                file_name=attachment.file_name,
                mime_type=attachment.mime_type,
                size_bytes=attachment.size_bytes,
            )
        )

    conversation.last_message_at = message.created_at if message.created_at else datetime.now(UTC)

    await record_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action="message.sent",
        resource_type="message",
        resource_id=str(message.id),
        metadata={"conversation_id": str(conversation_id), "sender_type": body.sender_type},
    )
    await db.commit()
    return await repository.get_message(db, tenant_id, message.id)


async def mark_read(
    db: AsyncSession, *, tenant_id: uuid.UUID, message_id: uuid.UUID, actor_user_id: uuid.UUID | None
) -> Message:
    message = await repository.get_message(db, tenant_id, message_id)
    if message is None:
        raise NotFoundError("Message not found")
    if message.read_at is not None:
        raise ConflictError("Message is already marked read")

    message.read_at = datetime.now(UTC)
    await record_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action="message.read",
        resource_type="message",
        resource_id=str(message.id),
        metadata={},
    )
    await db.commit()
    await db.refresh(message)
    return message
