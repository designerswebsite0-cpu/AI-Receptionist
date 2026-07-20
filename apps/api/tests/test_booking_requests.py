"""Booking Management (Phase X Stage 5) tests — the thin read/update
surface over app.orchestration.models.ServiceRequest scoped to
request_type == "booking_enquiry". Requires a reachable Postgres (see
conftest.db_engine); skips cleanly when none is available.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversations import service as conversation_service
from app.conversations.schemas import ConversationCreateRequest
from app.customers import service as customer_service
from app.customers.schemas import CustomerCreateRequest
from app.errors import NotFoundError
from app.orchestration import service as orchestration_service
from app.service_requests import repository, service
from app.service_requests.schemas import BookingRequestOut, BookingRequestUpdateRequest


async def _make_booking_request(db: AsyncSession, *, request_type: str = "booking_enquiry"):
    customer = await customer_service.create_customer(
        db, body=CustomerCreateRequest(full_name="Booking Guest"), actor_user_id=None
    )
    conversation = await conversation_service.create_conversation(
        db, body=ConversationCreateRequest(customer_id=customer.id, channel="webchat"), actor_user_id=None
    )
    request = await orchestration_service.create_service_request(
        db,
        conversation_id=conversation.id,
        customer_id=customer.id,
        request_type=request_type,
        details={"check_in_date": "15 July 2026", "adults": 2},
        created_by="ai",
        actor_user_id=None,
    )
    return customer, request


@pytest.mark.asyncio
async def test_get_booking_request_flattens_details_into_fixed_fields(db_session: AsyncSession):
    _, request = await _make_booking_request(db_session)

    fetched = await service.get_booking_request_or_404(db_session, request.id)
    out = BookingRequestOut.from_service_request(fetched)

    assert out.check_in_date == "15 July 2026"
    assert out.adults == 2
    assert out.booking_status is None
    assert out.status == "open"


@pytest.mark.asyncio
async def test_get_booking_request_rejects_non_booking_request_types(db_session: AsyncSession):
    _, request = await _make_booking_request(db_session, request_type="dining_enquiry")

    with pytest.raises(NotFoundError):
        await service.get_booking_request_or_404(db_session, request.id)


@pytest.mark.asyncio
async def test_get_booking_request_404s_for_unknown_id(db_session: AsyncSession):
    with pytest.raises(NotFoundError):
        await service.get_booking_request_or_404(db_session, uuid.uuid4())


@pytest.mark.asyncio
async def test_update_booking_request_merges_details_without_clobbering_original(db_session: AsyncSession):
    _, request = await _make_booking_request(db_session)

    updated = await service.update_booking_request(
        db_session,
        request_id=request.id,
        body=BookingRequestUpdateRequest(booking_status="confirmed", staff_notes="Called guest, confirmed by phone"),
        actor_user_id=None,
    )

    assert updated.details["booking_status"] == "confirmed"
    assert updated.details["staff_notes"] == "Called guest, confirmed by phone"
    assert updated.details["check_in_date"] == "15 July 2026"  # untouched


@pytest.mark.asyncio
async def test_update_booking_request_can_reassign_and_change_status(db_session: AsyncSession):
    customer, request = await _make_booking_request(db_session)

    updated = await service.update_booking_request(
        db_session,
        request_id=request.id,
        body=BookingRequestUpdateRequest(status="resolved", assigned_agent_id=None),
        actor_user_id=None,
    )

    assert updated.status == "resolved"
    assert updated.assigned_agent_id is None


@pytest.mark.asyncio
async def test_list_booking_requests_excludes_other_request_types(db_session: AsyncSession):
    _, booking = await _make_booking_request(db_session)
    await _make_booking_request(db_session, request_type="spa_enquiry")

    requests, total = await repository.list_booking_requests(db_session)

    assert all(r.request_type == "booking_enquiry" for r in requests)
    assert booking.id in [r.id for r in requests]
    assert total >= 1


@pytest.mark.asyncio
async def test_list_booking_requests_filters_by_booking_status(db_session: AsyncSession):
    _, confirmed = await _make_booking_request(db_session)
    await service.update_booking_request(
        db_session, request_id=confirmed.id, body=BookingRequestUpdateRequest(booking_status="confirmed"),
        actor_user_id=None,
    )
    _, _pending = await _make_booking_request(db_session)

    confirmed_only, total = await repository.list_booking_requests(db_session, booking_status="confirmed")

    assert total == len(confirmed_only)
    assert all(r.details.get("booking_status") == "confirmed" for r in confirmed_only)
