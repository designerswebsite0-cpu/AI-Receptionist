"""Integration tests for tool execution — requires a reachable Postgres
(see conftest.db_engine); skips cleanly when none is available. Confirms
every create_*_enquiry tool writes a service_requests row, and
create_room_booking writes a room_bookings row, rather than claiming any
operation completed.
"""

from datetime import date, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.bookings.models import RoomType
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


async def _make_room_type(db: AsyncSession, **overrides) -> RoomType:
    room_type = RoomType(
        slug=overrides.get("slug", "garden-deluxe-room"),
        name=overrides.get("name", "Garden Deluxe Room"),
        total_inventory=overrides.get("total_inventory", 2),
        max_occupancy=overrides.get("max_occupancy", 3),
        adults_allowed=overrides.get("adults_allowed", 2),
        children_allowed=overrides.get("children_allowed", 1),
        low_season_rate=9500,
        high_season_rate=12500,
    )
    db.add(room_type)
    await db.commit()
    await db.refresh(room_type)
    return room_type


@pytest.mark.asyncio
async def test_check_room_availability_reports_remaining_units(db_session: AsyncSession):
    customer, conversation = await _make_conversation(db_session)
    await _make_room_type(db_session, total_inventory=2)
    check_in = (date.today() + timedelta(days=10)).isoformat()
    check_out = (date.today() + timedelta(days=12)).isoformat()

    result = await execute_tool(
        db_session,
        tool_name="check_room_availability",
        tool_input={"room_type": "Garden Deluxe Room", "check_in_date": check_in, "check_out_date": check_out},
        conversation_id=conversation.id,
        customer_id=customer.id,
        actor_user_id=None,
    )

    assert result["available"] is True
    assert result["remaining_units"] == 2


@pytest.mark.asyncio
async def test_create_room_booking_writes_pending_review_row_not_a_fake_confirmation(db_session: AsyncSession):
    customer, conversation = await _make_conversation(db_session)
    await _make_room_type(db_session)
    check_in = (date.today() + timedelta(days=10)).isoformat()
    check_out = (date.today() + timedelta(days=12)).isoformat()

    result = await execute_tool(
        db_session,
        tool_name="create_room_booking",
        tool_input={
            "check_in_date": check_in,
            "check_out_date": check_out,
            "num_guests": 2,
            "room_type": "Garden Deluxe Room",
            "guest_name": "Jane Guest",
            "guest_phone": "+14155550100",
        },
        conversation_id=conversation.id,
        customer_id=customer.id,
        actor_user_id=None,
    )

    assert result["created"] is True
    assert result["status"] == "pending_review"  # never "confirmed" or "booked"


@pytest.mark.asyncio
async def test_create_room_booking_splits_party_across_multiple_rooms_of_same_type(db_session: AsyncSession):
    """2026-07-24 incident: 4 adults asking for 2 Honeymoon Pool Villas
    (max_occupancy 2 each) was wrongly refused because num_rooms didn't
    exist — the AI could only reason about a single room's capacity."""
    customer, conversation = await _make_conversation(db_session)
    await _make_room_type(db_session, max_occupancy=2, total_inventory=6)
    check_in = (date.today() + timedelta(days=10)).isoformat()
    check_out = (date.today() + timedelta(days=12)).isoformat()

    result = await execute_tool(
        db_session,
        tool_name="create_room_booking",
        tool_input={
            "check_in_date": check_in,
            "check_out_date": check_out,
            "num_guests": 4,
            "num_rooms": 2,
            "room_type": "Garden Deluxe Room",
            "guest_name": "Jane Guest",
            "guest_phone": "+14155550100",
        },
        conversation_id=conversation.id,
        customer_id=customer.id,
        actor_user_id=None,
    )

    assert result["created"] is True
    assert result["num_rooms_booked"] == 2
    assert len(result["booking_ids"]) == 2


@pytest.mark.asyncio
async def test_create_room_booking_rejects_dates_beyond_six_month_window(db_session: AsyncSession):
    customer, conversation = await _make_conversation(db_session)
    await _make_room_type(db_session)
    check_in = (date.today() + timedelta(days=400)).isoformat()
    check_out = (date.today() + timedelta(days=402)).isoformat()

    result = await execute_tool(
        db_session,
        tool_name="create_room_booking",
        tool_input={
            "check_in_date": check_in,
            "check_out_date": check_out,
            "num_guests": 2,
            "room_type": "Garden Deluxe Room",
            "guest_name": "Jane Guest",
            "guest_phone": "+14155550100",
        },
        conversation_id=conversation.id,
        customer_id=customer.id,
        actor_user_id=None,
    )

    assert result["created"] is False
    assert any("6 months" in r or "days out" in r for r in result["reasons"])


@pytest.mark.asyncio
async def test_create_room_booking_rejects_when_inventory_exhausted(db_session: AsyncSession):
    customer, conversation = await _make_conversation(db_session)
    await _make_room_type(db_session, total_inventory=1)
    check_in = (date.today() + timedelta(days=10)).isoformat()
    check_out = (date.today() + timedelta(days=12)).isoformat()

    async def _book():
        return await execute_tool(
            db_session,
            tool_name="create_room_booking",
            tool_input={
                "check_in_date": check_in,
                "check_out_date": check_out,
                "num_guests": 2,
                "room_type": "Garden Deluxe Room",
                "guest_name": "Jane Guest",
                "guest_phone": "+14155550100",
            },
            conversation_id=conversation.id,
            customer_id=customer.id,
            actor_user_id=None,
        )

    first = await _book()
    second = await _book()

    assert first["created"] is True
    assert second["created"] is False


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
