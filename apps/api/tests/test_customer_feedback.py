"""Customer Feedback (Phase X Stage 7) tests. Requires a reachable Postgres
(see conftest.db_engine); skips cleanly when none is available.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversations import service as conversation_service
from app.conversations.schemas import ConversationCreateRequest
from app.customers import service as customer_service
from app.customers.schemas import CustomerCreateRequest
from app.errors import NotFoundError
from app.feedback import repository, service
from app.feedback.schemas import FeedbackUpdateRequest


async def _make_conversation(db: AsyncSession):
    customer = await customer_service.create_customer(
        db, body=CustomerCreateRequest(full_name="Feedback Guest"), actor_user_id=None
    )
    conversation = await conversation_service.create_conversation(
        db, body=ConversationCreateRequest(customer_id=customer.id, channel="webchat"), actor_user_id=None
    )
    return customer, conversation


@pytest.mark.asyncio
async def test_record_webchat_feedback_creates_website_chat_row(db_session: AsyncSession):
    customer, conversation = await _make_conversation(db_session)

    feedback = await service.record_webchat_feedback(
        db_session,
        rating="up",
        comment="Fast and helpful",
        conversation_id=conversation.id,
        customer_id=customer.id,
        turn_id=None,
    )

    assert feedback.category == "website_chat"
    assert feedback.rating == "up"
    assert feedback.status == "new"
    assert feedback.comment == "Fast and helpful"


@pytest.mark.asyncio
async def test_get_feedback_404s_for_unknown_id(db_session: AsyncSession):
    with pytest.raises(NotFoundError):
        await service.get_feedback_or_404(db_session, uuid.uuid4())


@pytest.mark.asyncio
async def test_update_feedback_only_touches_provided_fields(db_session: AsyncSession):
    _, conversation = await _make_conversation(db_session)
    feedback = await service.record_webchat_feedback(
        db_session, rating="down", comment="Slow reply", conversation_id=conversation.id,
        customer_id=conversation.customer_id, turn_id=None,
    )

    updated = await service.update_feedback(
        db_session, feedback_id=feedback.id, body=FeedbackUpdateRequest(status="reviewed")
    )

    assert updated.status == "reviewed"
    assert updated.comment == "Slow reply"  # untouched


@pytest.mark.asyncio
async def test_list_feedback_filters_by_rating(db_session: AsyncSession):
    _, conversation = await _make_conversation(db_session)
    await service.record_webchat_feedback(
        db_session, rating="up", comment=None, conversation_id=conversation.id,
        customer_id=conversation.customer_id, turn_id=None,
    )
    await service.record_webchat_feedback(
        db_session, rating="down", comment=None, conversation_id=conversation.id,
        customer_id=conversation.customer_id, turn_id=None,
    )

    down_only, total = await repository.list_feedback(db_session, rating="down")

    assert total == len(down_only)
    assert all(f.rating == "down" for f in down_only)


@pytest.mark.asyncio
async def test_get_stats_counts_up_and_down(db_session: AsyncSession):
    _, conversation = await _make_conversation(db_session)
    await service.record_webchat_feedback(
        db_session, rating="up", comment=None, conversation_id=conversation.id,
        customer_id=conversation.customer_id, turn_id=None,
    )
    await service.record_webchat_feedback(
        db_session, rating="up", comment=None, conversation_id=conversation.id,
        customer_id=conversation.customer_id, turn_id=None,
    )
    await service.record_webchat_feedback(
        db_session, rating="down", comment=None, conversation_id=conversation.id,
        customer_id=conversation.customer_id, turn_id=None,
    )

    up_count, down_count, total, by_category = await repository.get_stats(db_session)

    assert up_count >= 2
    assert down_count >= 1
    assert total == up_count + down_count
    assert by_category.get("website_chat", 0) >= 3
