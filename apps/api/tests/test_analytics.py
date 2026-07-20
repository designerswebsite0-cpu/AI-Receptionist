"""Dashboard & Analytics (Phase X Stage 9) tests — every number must trace
back to a real row in an existing table. Requires a reachable Postgres
(see conftest.db_engine); skips cleanly when none is available.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics import service
from app.conversations import service as conversation_service
from app.conversations.schemas import ConversationCreateRequest
from app.customers import service as customer_service
from app.customers.schemas import CustomerCreateRequest
from app.errors import ValidationErrorApp
from app.feedback import service as feedback_service
from app.orchestration import service as orchestration_service


def test_resolve_range_rejects_unknown_range_key():
    with pytest.raises(ValidationErrorApp):
        service.resolve_range("last_quarter", None, None)


def test_resolve_range_requires_start_and_end_for_custom():
    with pytest.raises(ValidationErrorApp):
        service.resolve_range("custom", None, None)


def test_resolve_range_rejects_start_after_end():
    now = datetime.now(UTC)
    with pytest.raises(ValidationErrorApp):
        service.resolve_range("custom", now, now - timedelta(days=1))


def test_resolve_range_today_starts_at_midnight():
    start, end = service.resolve_range("today", None, None)
    assert start.hour == 0 and start.minute == 0 and start.second == 0
    assert start <= end


@pytest.mark.asyncio
async def test_get_dashboard_analytics_counts_real_conversation(db_session: AsyncSession):
    customer = await customer_service.create_customer(
        db_session, body=CustomerCreateRequest(full_name="Analytics Guest"), actor_user_id=None
    )
    conversation = await conversation_service.create_conversation(
        db_session, body=ConversationCreateRequest(customer_id=customer.id, channel="webchat"), actor_user_id=None
    )
    await orchestration_service.create_service_request(
        db_session,
        conversation_id=conversation.id,
        customer_id=customer.id,
        request_type="booking_enquiry",
        details={"check_in_date": "1 Aug 2026"},
        created_by="ai",
        actor_user_id=None,
    )
    await feedback_service.record_webchat_feedback(
        db_session, rating="up", comment=None, conversation_id=conversation.id,
        customer_id=customer.id, turn_id=None,
    )

    analytics = await service.get_dashboard_analytics(db_session, range_key="today", start=None, end=None)

    assert analytics.summary.total_conversations >= 1
    assert analytics.summary.new_customers >= 1
    assert analytics.summary.booking_enquiries >= 1
    assert analytics.summary.feedback_total >= 1
    assert analytics.summary.feedback_positive_rate is not None
    assert any(row.count >= 1 for row in analytics.conversations_by_day)


@pytest.mark.asyncio
async def test_get_dashboard_analytics_custom_range_excludes_outside_data(db_session: AsyncSession):
    far_future_start = datetime.now(UTC) + timedelta(days=365)
    far_future_end = far_future_start + timedelta(days=1)

    analytics = await service.get_dashboard_analytics(
        db_session, range_key="custom", start=far_future_start, end=far_future_end
    )

    assert analytics.summary.total_conversations == 0
    assert analytics.summary.new_customers == 0
    assert analytics.summary.booking_enquiries == 0
    assert analytics.conversations_by_day == []
