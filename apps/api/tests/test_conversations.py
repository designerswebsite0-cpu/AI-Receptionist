"""Conversation lifecycle, messages, and dialogue-state engine tests.
Requires a reachable Postgres (see conftest.db_engine); skips cleanly when
none is available.

Single-resort deployment (product_decisions.md): no tenant_id anywhere.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversations import service as conversation_service
from app.conversations import state_machine
from app.conversations.schemas import ConversationCreateRequest
from app.customers import service as customer_service
from app.customers.schemas import CustomerCreateRequest
from app.errors import ConflictError, NotFoundError
from app.messages import service as message_service
from app.messages.schemas import MessageCreateRequest


async def _make_customer(db: AsyncSession):
    return await customer_service.create_customer(db, body=CustomerCreateRequest(), actor_user_id=None)


@pytest.mark.asyncio
async def test_create_conversation_defaults(db_session: AsyncSession):
    customer = await _make_customer(db_session)

    conversation = await conversation_service.create_conversation(
        db_session,
        body=ConversationCreateRequest(customer_id=customer.id, channel="webchat"),
        actor_user_id=None,
    )

    assert conversation.status == "open"
    assert conversation.current_state == "greeting"
    assert conversation.ai_active is True
    assert conversation.human_active is False


@pytest.mark.asyncio
async def test_status_transitions_set_active_flags(db_session: AsyncSession):
    customer = await _make_customer(db_session)
    conversation = await conversation_service.create_conversation(
        db_session,
        body=ConversationCreateRequest(customer_id=customer.id, channel="whatsapp"),
        actor_user_id=None,
    )

    handled = await conversation_service.change_status(
        db_session, conversation_id=conversation.id, new_status="human_handling", actor_user_id=None
    )
    assert handled.ai_active is False
    assert handled.human_active is True

    closed = await conversation_service.close_conversation(
        db_session, conversation_id=conversation.id, actor_user_id=None
    )
    assert closed.status == "closed"
    assert closed.closed_at is not None


@pytest.mark.asyncio
async def test_dialogue_state_transition_is_logged(db_session: AsyncSession):
    customer = await _make_customer(db_session)
    conversation = await conversation_service.create_conversation(
        db_session,
        body=ConversationCreateRequest(customer_id=customer.id, channel="webchat"),
        actor_user_id=None,
    )

    updated = await conversation_service.change_dialogue_state(
        db_session,
        conversation_id=conversation.id,
        new_state="booking",
        changed_by="ai",
        metadata={"reason": "guest asked to book"},
        actor_user_id=None,
    )
    assert updated.current_state == "booking"

    history = await state_machine.get_state_history(db_session, conversation.id)
    assert len(history) == 1
    assert history[0].from_state == "greeting"
    assert history[0].to_state == "booking"
    assert history[0].changed_by == "ai"


@pytest.mark.asyncio
async def test_nonexistent_conversation_is_not_found(db_session: AsyncSession):
    with pytest.raises(NotFoundError):
        await conversation_service.get_conversation_or_404(db_session, uuid.uuid4())


@pytest.mark.asyncio
async def test_send_message_updates_last_message_at_and_direction(db_session: AsyncSession):
    customer = await _make_customer(db_session)
    conversation = await conversation_service.create_conversation(
        db_session,
        body=ConversationCreateRequest(customer_id=customer.id, channel="webchat"),
        actor_user_id=None,
    )
    assert conversation.last_message_at is None

    message = await message_service.send_message(
        db_session,
        conversation_id=conversation.id,
        body=MessageCreateRequest(sender_type="customer", content_text="Hi, is the pool open?"),
        actor_user_id=None,
    )
    assert message.direction == "inbound"
    assert message.delivery_status == "delivered"

    refreshed = await conversation_service.get_conversation_or_404(db_session, conversation.id)
    assert refreshed.last_message_at is not None


@pytest.mark.asyncio
async def test_send_message_with_external_id_is_idempotent(db_session: AsyncSession):
    customer = await _make_customer(db_session)
    conversation = await conversation_service.create_conversation(
        db_session,
        body=ConversationCreateRequest(customer_id=customer.id, channel="whatsapp"),
        actor_user_id=None,
    )

    body = MessageCreateRequest(sender_type="customer", content_text="Hello", external_message_id="wamid.ABC123")
    first = await message_service.send_message(
        db_session, conversation_id=conversation.id, body=body, actor_user_id=None
    )
    second = await message_service.send_message(
        db_session, conversation_id=conversation.id, body=body, actor_user_id=None
    )

    assert first.id == second.id


@pytest.mark.asyncio
async def test_mark_read_twice_conflicts(db_session: AsyncSession):
    customer = await _make_customer(db_session)
    conversation = await conversation_service.create_conversation(
        db_session,
        body=ConversationCreateRequest(customer_id=customer.id, channel="webchat"),
        actor_user_id=None,
    )
    message = await message_service.send_message(
        db_session,
        conversation_id=conversation.id,
        body=MessageCreateRequest(sender_type="human", content_text="We're on it!"),
        actor_user_id=None,
    )

    await message_service.mark_read(db_session, message_id=message.id, actor_user_id=None)
    with pytest.raises(ConflictError):
        await message_service.mark_read(db_session, message_id=message.id, actor_user_id=None)
