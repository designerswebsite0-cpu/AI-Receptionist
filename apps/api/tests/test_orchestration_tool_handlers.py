"""Integration tests for tool execution — requires a reachable Postgres
(see conftest.db_engine); skips cleanly when none is available. Confirms
every create_*_enquiry tool writes a service_requests row rather than
claiming any operation completed.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversations import service as conversation_service
from app.conversations.schemas import ConversationCreateRequest
from app.customers import service as customer_service
from app.customers.schemas import CustomerCreateRequest
from app.orchestration import repository
from app.orchestration.tools.handlers import execute_tool


async def _make_conversation(db: AsyncSession):
    customer = await customer_service.create_customer(
        db, body=CustomerCreateRequest(full_name="Jane Guest"), actor_user_id=None
    )
    conversation = await conversation_service.create_conversation(
        db, body=ConversationCreateRequest(customer_id=customer.id, channel="webchat"), actor_user_id=None
    )
    return customer, conversation


@pytest.mark.asyncio
async def test_create_booking_enquiry_writes_service_request_not_a_fake_booking(db_session: AsyncSession):
    customer, conversation = await _make_conversation(db_session)

    result = await execute_tool(
        db_session,
        tool_name="create_booking_enquiry",
        tool_input={"check_in_date": "15 July 2026", "adults": 2},
        conversation_id=conversation.id,
        customer_id=customer.id,
        actor_user_id=None,
    )

    assert result["status"] == "open"  # never "confirmed" or "booked"
    assert result["request_type"] == "booking_enquiry"

    requests = await repository.list_service_requests_for_conversation(db_session, conversation.id)
    assert len(requests) == 1
    assert requests[0].details["check_in_date"] == "15 July 2026"
    assert requests[0].created_by == "ai"


@pytest.mark.asyncio
async def test_read_guest_profile_returns_real_customer_data(db_session: AsyncSession):
    customer, conversation = await _make_conversation(db_session)

    result = await execute_tool(
        db_session, tool_name="read_guest_profile", tool_input={}, conversation_id=conversation.id,
        customer_id=customer.id, actor_user_id=None,
    )

    assert result["full_name"] == "Jane Guest"


@pytest.mark.asyncio
async def test_update_guest_preferences_merges_into_existing_preferences(db_session: AsyncSession):
    customer, conversation = await _make_conversation(db_session)

    await execute_tool(
        db_session, tool_name="update_guest_preferences", tool_input={"preferences": {"room_view": "ocean"}},
        conversation_id=conversation.id, customer_id=customer.id, actor_user_id=None,
    )
    result = await execute_tool(
        db_session, tool_name="update_guest_preferences", tool_input={"preferences": {"dietary": "vegan"}},
        conversation_id=conversation.id, customer_id=customer.id, actor_user_id=None,
    )

    assert result["resort_preferences"] == {"room_view": "ocean", "dietary": "vegan"}


@pytest.mark.asyncio
async def test_request_human_assistance_creates_request_and_signals_handoff(db_session: AsyncSession):
    customer, conversation = await _make_conversation(db_session)

    result = await execute_tool(
        db_session, tool_name="request_human_assistance", tool_input={"reason": "Wants to speak to a manager"},
        conversation_id=conversation.id, customer_id=customer.id, actor_user_id=None,
    )

    assert result["handoff_requested"] is True
    requests = await repository.list_service_requests_for_conversation(db_session, conversation.id)
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_retrieve_request_status_for_existing_request(db_session: AsyncSession):
    customer, conversation = await _make_conversation(db_session)
    created = await execute_tool(
        db_session, tool_name="create_spa_enquiry", tool_input={"service": "deep tissue massage"},
        conversation_id=conversation.id, customer_id=customer.id, actor_user_id=None,
    )

    status = await execute_tool(
        db_session, tool_name="retrieve_request_status", tool_input={"request_id": created["service_request_id"]},
        conversation_id=conversation.id, customer_id=customer.id, actor_user_id=None,
    )

    assert status["found"] is True
    assert status["request_type"] == "spa_enquiry"


@pytest.mark.asyncio
async def test_retrieve_request_status_for_request_from_a_different_conversation_is_not_found(
    db_session: AsyncSession,
):
    customer, conversation = await _make_conversation(db_session)
    _, other_conversation = await _make_conversation(db_session)

    created = await execute_tool(
        db_session, tool_name="create_activity_enquiry", tool_input={"activity": "nature walk"},
        conversation_id=conversation.id, customer_id=customer.id, actor_user_id=None,
    )

    status = await execute_tool(
        db_session, tool_name="retrieve_request_status", tool_input={"request_id": created["service_request_id"]},
        conversation_id=other_conversation.id, customer_id=customer.id, actor_user_id=None,
    )

    assert status["found"] is False


@pytest.mark.asyncio
async def test_retrieve_request_status_with_malformed_id_does_not_crash(db_session: AsyncSession):
    customer, conversation = await _make_conversation(db_session)

    status = await execute_tool(
        db_session, tool_name="retrieve_request_status", tool_input={"request_id": "not-a-uuid"},
        conversation_id=conversation.id, customer_id=customer.id, actor_user_id=None,
    )

    assert status["found"] is False


@pytest.mark.asyncio
async def test_unknown_tool_name_raises_clear_error(db_session: AsyncSession):
    customer, conversation = await _make_conversation(db_session)
    with pytest.raises(ValueError, match="No handler registered"):
        await execute_tool(
            db_session, tool_name="search_resort_knowledge", tool_input={"query": "x"},
            conversation_id=conversation.id, customer_id=customer.id, actor_user_id=None,
        )
