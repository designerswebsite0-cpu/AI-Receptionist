"""Tool execution — one handler per tool name, called only after
app.orchestration.tools.validation.validate_tool_call has already
approved the call. Every create_*_enquiry handler writes a
service_requests row (never a fake completed booking/payment/refund);
read_guest_profile/retrieve_request_status are read-only;
request_human_assistance both records an enquiry AND signals the pipeline
to trigger a real handoff.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.customers.service import get_customer_or_404
from app.orchestration import repository, service

_ENQUIRY_REQUEST_TYPES = {
    "create_booking_enquiry": "booking_enquiry",
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
    }.get(tool_name)

    if handler is None:
        raise ValueError(
            f"No handler registered for tool '{tool_name}' "
            "(search_resort_knowledge is handled by the pipeline directly)"
        )

    return await handler(
        db, tool_input=tool_input, conversation_id=conversation_id, customer_id=customer_id, actor_user_id=actor_user_id
    )
