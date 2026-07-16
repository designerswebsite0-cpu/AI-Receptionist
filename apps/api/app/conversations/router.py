import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import PageParams, build_page_meta
from app.common.responses import success
from app.conversations import repository, service
from app.conversations.constants import CHANNELS, STATUSES
from app.conversations.schemas import (
    AssignRequest,
    ConversationCreateRequest,
    ConversationOut,
    ConversationUpdateRequest,
    StateChangeRequest,
    StatusChangeRequest,
)
from app.database import get_db
from app.deps import get_current_user
from app.errors import ValidationErrorApp
from app.messages import repository as messages_repository
from app.messages import service as messages_service
from app.messages.schemas import MessageCreateRequest, MessageOut
from app.users.models import User

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


@router.post("")
async def create_conversation(
    body: ConversationCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    conversation = await service.create_conversation(db, body=body, actor_user_id=user.id)
    return success(_conversation_payload(conversation))


@router.get("")
async def list_conversations(
    status: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    assigned_agent_id: uuid.UUID | None = Query(default=None),
    customer_id: uuid.UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if status is not None and status not in STATUSES:
        raise ValidationErrorApp(f"status must be one of {STATUSES}")
    if channel is not None and channel not in CHANNELS:
        raise ValidationErrorApp(f"channel must be one of {CHANNELS}")

    params = PageParams(page=page, page_size=page_size)
    conversations, total = await repository.search_conversations(
        db,
        status=status,
        channel=channel,
        assigned_agent_id=assigned_agent_id,
        customer_id=customer_id,
        offset=params.offset,
        limit=params.page_size,
    )
    return success(
        {
            "items": [_conversation_payload(c) for c in conversations],
            "meta": build_page_meta(params, total).model_dump(),
        }
    )


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    conversation = await service.get_conversation_or_404(db, conversation_id)
    return success(_conversation_payload(conversation))


@router.patch("/{conversation_id}")
async def update_conversation(
    conversation_id: uuid.UUID,
    body: ConversationUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    conversation = await service.update_conversation(
        db, conversation_id=conversation_id, body=body, actor_user_id=user.id
    )
    return success(_conversation_payload(conversation))


@router.post("/{conversation_id}/assign")
async def assign_conversation(
    conversation_id: uuid.UUID,
    body: AssignRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    conversation = await service.assign_conversation(
        db, conversation_id=conversation_id, agent_user_id=body.agent_user_id, actor_user_id=user.id
    )
    return success(_conversation_payload(conversation))


@router.post("/{conversation_id}/status")
async def change_status(
    conversation_id: uuid.UUID,
    body: StatusChangeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    conversation = await service.change_status(
        db, conversation_id=conversation_id, new_status=body.status, actor_user_id=user.id
    )
    return success(_conversation_payload(conversation))


@router.post("/{conversation_id}/close")
async def close_conversation(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    conversation = await service.close_conversation(db, conversation_id=conversation_id, actor_user_id=user.id)
    return success(_conversation_payload(conversation))


@router.post("/{conversation_id}/state")
async def change_dialogue_state(
    conversation_id: uuid.UUID,
    body: StateChangeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    conversation = await service.change_dialogue_state(
        db,
        conversation_id=conversation_id,
        new_state=body.state,
        changed_by=body.changed_by,
        metadata=body.metadata,
        actor_user_id=user.id,
    )
    return success(_conversation_payload(conversation))


@router.get("/{conversation_id}/messages")
async def list_messages(
    conversation_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await service.get_conversation_or_404(db, conversation_id)
    params = PageParams(page=page, page_size=page_size)
    messages, total = await messages_repository.list_messages(
        db, conversation_id, offset=params.offset, limit=params.page_size
    )
    return success(
        {
            "items": [MessageOut.model_validate(m).model_dump(mode="json") for m in messages],
            "meta": build_page_meta(params, total).model_dump(),
        }
    )


@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: uuid.UUID,
    body: MessageCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    message = await messages_service.send_message(
        db, conversation_id=conversation_id, body=body, actor_user_id=user.id
    )
    return success(MessageOut.model_validate(message).model_dump(mode="json"))


@router.post("/{conversation_id}/messages/{message_id}/read")
async def mark_message_read(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    message = await messages_service.mark_read(db, message_id=message_id, actor_user_id=user.id)
    return success(MessageOut.model_validate(message).model_dump(mode="json"))


def _conversation_payload(conversation) -> dict:
    return ConversationOut.model_validate(conversation).model_dump(mode="json")
