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
    db: AsyncSession, *, conversation_id: uuid.UUID, body: MessageCreateRequest, actor_user_id: uuid.UUID | None
) -> Message:
    conversation = await get_conversation_or_404(db, conversation_id)

    if body.external_message_id:
        existing = await repository.find_by_external_id(db, body.external_message_id)
        if existing is not None:
            # Idempotent replay (rules.md §13): return the already-recorded
            # message instead of creating a duplicate.
            return existing

    direction = "inbound" if body.sender_type == "customer" else "outbound"
    message = Message(
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
        actor_user_id=actor_user_id,
        action="message.sent",
        resource_type="message",
        resource_id=str(message.id),
        metadata={"conversation_id": str(conversation_id), "sender_type": body.sender_type},
    )
    await db.commit()
    return await repository.get_message(db, message.id)


async def mark_read(db: AsyncSession, *, message_id: uuid.UUID, actor_user_id: uuid.UUID | None) -> Message:
    message = await repository.get_message(db, message_id)
    if message is None:
        raise NotFoundError("Message not found")
    if message.read_at is not None:
        raise ConflictError("Message is already marked read")

    message.read_at = datetime.now(UTC)
    await record_audit_event(
        db,
        actor_user_id=actor_user_id,
        action="message.read",
        resource_type="message",
        resource_id=str(message.id),
        metadata={},
    )
    await db.commit()
    await db.refresh(message)
    return message


async def mark_conversation_read(
    db: AsyncSession, *, conversation_id: uuid.UUID, actor_user_id: uuid.UUID | None
) -> int:
    """Inbox-level "mark read" — bulk version of mark_read, since a staff
    member opening a thread (or explicitly clearing its unread state)
    means every unread message in it, not one at a time."""
    await get_conversation_or_404(db, conversation_id)
    changed = await repository.mark_all_read(db, conversation_id)
    if changed:
        await record_audit_event(
            db,
            actor_user_id=actor_user_id,
            action="conversation.marked_read",
            resource_type="conversation",
            resource_id=str(conversation_id),
            metadata={"messages_marked": changed},
        )
        await db.commit()
    return changed


async def mark_conversation_unread(
    db: AsyncSession, *, conversation_id: uuid.UUID, actor_user_id: uuid.UUID | None
) -> None:
    """Inbox-level "mark unread" — flags the conversation as needing
    another look by nulling the most recent guest/AI message's read_at
    (see repository.mark_latest_unread's docstring for why there's no
    separate unread flag/column)."""
    await get_conversation_or_404(db, conversation_id)
    message = await repository.mark_latest_unread(db, conversation_id)
    if message is not None:
        await record_audit_event(
            db,
            actor_user_id=actor_user_id,
            action="conversation.marked_unread",
            resource_type="conversation",
            resource_id=str(conversation_id),
            metadata={},
        )
        await db.commit()
