"""Tool execution — one handler per tool name, called only after
app.orchestration.tools.validation.validate_tool_call has already
approved the call. Every create_*_enquiry handler writes a
service_requests row (never a fake completed booking/payment/refund);
read_guest_profile/retrieve_request_status are read-only;
request_human_assistance both records an enquiry AND signals the pipeline
to trigger a real handoff. check_room_availability/create_room_booking are
Phase 7's dedicated room-booking flow (app.bookings) — a separate table
from service_requests per the 2026-07-24 brief, not another enquiry type.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.bookings import service as bookings_service
from app.customers.service import get_customer_or_404
from app.orchestration import repository, service
from app.payments import service as payments_service

_ENQUIRY_REQUEST_TYPES = {
    "create_dining_enquiry": "dining_enquiry",
    "create_spa_enquiry": "spa_enquiry",
    "create_activity_enquiry": "activity_enquiry",
    "create_transfer_enquiry": "transfer_enquiry",
}


async def _handle_enquiry(
    db: AsyncSession, *, request_type: str, tool_input: dict, conversation_id: uuid.UUID, customer_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
) -> dict:
    request = await service.create_service_request(
        db,
        conversation_id=conversation_id,
        customer_id=customer_id,
        request_type=request_type,
        details=tool_input,
        created_by="ai",
        actor_user_id=actor_user_id,
    )
    return {"service_request_id": str(request.id), "status": request.status, "request_type": request.request_type}


async def _handle_check_room_availability(
    db: AsyncSession, *, tool_input: dict, conversation_id: uuid.UUID, customer_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
) -> dict:
    return await bookings_service.check_availability(
        db,
        room_type=tool_input.get("room_type", ""),
        check_in_date=tool_input.get("check_in_date", ""),
        check_out_date=tool_input.get("check_out_date", ""),
    )


async def _handle_record_payment_enquiry(
    db: AsyncSession, *, tool_input: dict, conversation_id: uuid.UUID, customer_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
) -> dict:
    raw_booking_id = tool_input.get("room_booking_id")
    booking_id = None
    if raw_booking_id:
        try:
            booking_id = uuid.UUID(raw_booking_id)
        except (ValueError, TypeError):
            booking_id = None
    payment = await payments_service.record_payment_enquiry(
        db,
        conversation_id=conversation_id,
        customer_id=customer_id,
        room_booking_id=booking_id,
        amount=tool_input.get("amount"),
        notes=tool_input.get("notes"),
    )
    return {"payment_id": str(payment.id), "status": payment.status}


async def _handle_create_room_booking(
    db: AsyncSession, *, tool_input: dict, conversation_id: uuid.UUID, customer_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
) -> dict:
    result = await bookings_service.submit_booking_enquiry(
        db,
        conversation_id=conversation_id,
        customer_id=customer_id,
        check_in_date=tool_input.get("check_in_date", ""),
        check_out_date=tool_input.get("check_out_date", ""),
        num_guests=tool_input.get("num_guests"),
        room_type=tool_input.get("room_type", ""),
        guest_name=tool_input.get("guest_name", ""),
        guest_phone=tool_input.get("guest_phone", ""),
        breakfast_included=tool_input.get("breakfast_included"),
        special_preferences=tool_input.get("special_preferences"),
    )
    if not result.created:
        return {"created": False, "reasons": result.reasons}
    return {"created": True, "booking_id": str(result.booking_id), "status": result.status}


async def _handle_read_guest_profile(
    db: AsyncSession, *, tool_input: dict, conversation_id: uuid.UUID, customer_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
) -> dict:
    customer = await get_customer_or_404(db, customer_id)
    return {
        "full_name": customer.full_name,
        "preferred_language": customer.preferred_language,
        "loyalty_reference": customer.loyalty_reference,
        "resort_preferences": customer.resort_preferences,
    }


async def _handle_update_guest_preferences(
    db: AsyncSession, *, tool_input: dict, conversation_id: uuid.UUID, customer_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
) -> dict:
    customer = await get_customer_or_404(db, customer_id)
    new_preferences = tool_input.get("preferences") or {}
    customer.resort_preferences = {**(customer.resort_preferences or {}), **new_preferences}
    await db.commit()
    await db.refresh(customer)
    return {"updated": True, "resort_preferences": customer.resort_preferences}


async def _handle_record_complaint(
    db: AsyncSession, *, tool_input: dict, conversation_id: uuid.UUID, customer_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
) -> dict:
    request = await service.create_service_request(
        db,
        conversation_id=conversation_id,
        customer_id=customer_id,
        request_type="complaint",
        details=tool_input,
        created_by="ai",
        actor_user_id=actor_user_id,
    )
    return {"service_request_id": str(request.id), "status": request.status}


async def _handle_request_human_assistance(
    db: AsyncSession, *, tool_input: dict, conversation_id: uuid.UUID, customer_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
) -> dict:
    request = await service.create_service_request(
        db,
        conversation_id=conversation_id,
        customer_id=customer_id,
        request_type="service_request",
        details=tool_input,
        created_by="ai",
        actor_user_id=actor_user_id,
    )
    # handoff_requested=True is read by app.orchestration.pipeline to
    # actually trigger the handoff engine's transition — this handler
    # only records the intake, it never flips conversation state itself.
    return {"service_request_id": str(request.id), "handoff_requested": True, "reason": tool_input.get("reason")}


async def _handle_retrieve_request_status(
    db: AsyncSession, *, tool_input: dict, conversation_id: uuid.UUID, customer_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
) -> dict:
    raw_id = tool_input.get("request_id")
    try:
        request_id = uuid.UUID(raw_id)
    except (ValueError, TypeError):
        return {"found": False}

    request = await repository.get_service_request(db, request_id)
    if request is None or request.conversation_id != conversation_id:
        return {"found": False}
    return {"found": True, "status": request.status, "request_type": request.request_type}


async def execute_tool(
    db: AsyncSession,
    *,
    tool_name: str,
    tool_input: dict,
    conversation_id: uuid.UUID,
    customer_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
) -> dict:
    if tool_name in _ENQUIRY_REQUEST_TYPES:
        return await _handle_enquiry(
            db,
            request_type=_ENQUIRY_REQUEST_TYPES[tool_name],
            tool_input=tool_input,
            conversation_id=conversation_id,
            customer_id=customer_id,
            actor_user_id=actor_user_id,
        )

    handler = {
        "read_guest_profile": _handle_read_guest_profile,
        "update_guest_preferences": _handle_update_guest_preferences,
        "record_complaint": _handle_record_complaint,
        "request_human_assistance": _handle_request_human_assistance,
        "retrieve_request_status": _handle_retrieve_request_status,
        "check_room_availability": _handle_check_room_availability,
        "create_room_booking": _handle_create_room_booking,
        "record_payment_enquiry": _handle_record_payment_enquiry,
    }.get(tool_name)

    if handler is None:
        raise ValueError(
            f"No handler registered for tool '{tool_name}' "
            "(search_resort_knowledge is handled by the pipeline directly)"
        )

    return await handler(
        db, tool_input=tool_input, conversation_id=conversation_id, customer_id=customer_id, actor_user_id=actor_user_id
    )
