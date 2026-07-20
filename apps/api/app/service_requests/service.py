"""Booking Management (Phase X Stage 5): a thin read/update surface over
app.orchestration.models.ServiceRequest, scoped to request_type ==
"booking_enquiry". Reuses the existing generic enquiry table rather than a
dedicated bookings table — see app.orchestration.service.create_service_request,
which every create_booking_enquiry tool call already writes into. Nothing
here ever confirms a real reservation or checks live availability; it is
staff-facing intake triage only, same guarantee the orchestration layer
already makes.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_audit_event
from app.errors import NotFoundError
from app.orchestration import repository as orchestration_repository
from app.orchestration.models import ServiceRequest
from app.service_requests.constants import BOOKING_REQUEST_TYPE
from app.service_requests.schemas import BookingRequestUpdateRequest


async def get_booking_request_or_404(db: AsyncSession, request_id: uuid.UUID) -> ServiceRequest:
    request = await orchestration_repository.get_service_request(db, request_id)
    if request is None or request.request_type != BOOKING_REQUEST_TYPE:
        raise NotFoundError("Booking request not found")
    return request


async def update_booking_request(
    db: AsyncSession, *, request_id: uuid.UUID, body: BookingRequestUpdateRequest, actor_user_id: uuid.UUID | None
) -> ServiceRequest:
    request = await get_booking_request_or_404(db, request_id)
    updates = body.model_dump(exclude_unset=True)
    before_state = {
        "status": request.status,
        "assigned_agent_id": str(request.assigned_agent_id) if request.assigned_agent_id else None,
        "details": request.details,
    }

    if "status" in updates:
        request.status = updates["status"]
    if "assigned_agent_id" in updates:
        request.assigned_agent_id = updates["assigned_agent_id"]

    details_updates = {k: updates[k] for k in ("booking_status", "staff_notes") if k in updates}
    if details_updates:
        request.details = {**request.details, **details_updates}

    await record_audit_event(
        db,
        actor_user_id=actor_user_id,
        action="booking_request.updated",
        resource_type="service_request",
        resource_id=str(request.id),
        before_state=before_state,
        after_state={k: str(v) for k, v in updates.items()},
        metadata={"fields": list(updates.keys())},
    )
    await db.commit()
    await db.refresh(request)
    return request
