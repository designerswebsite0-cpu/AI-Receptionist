import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.orchestration.constants import SERVICE_REQUEST_STATUSES
from app.orchestration.models import ServiceRequest
from app.service_requests.constants import BOOKING_STATUSES


class BookingRequestOut(BaseModel):
    """Flattens ServiceRequest.details' free-form JSONB into the fixed
    fields a booking enquiry is known to carry (see the create_booking_enquiry
    tool schema, app/orchestration/tools/registry.py) — never claims a
    confirmed reservation or live availability, only what the guest/AI
    actually supplied for staff follow-up."""

    id: uuid.UUID
    conversation_id: uuid.UUID
    customer_id: uuid.UUID
    customer_name: str | None = None
    status: str
    booking_status: str | None
    check_in_date: str | None
    num_nights: int | None
    adults: int | None
    room_category: str | None
    staff_notes: str | None
    created_by: str
    assigned_agent_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_service_request(cls, request: ServiceRequest, *, customer_name: str | None = None) -> "BookingRequestOut":
        details = request.details or {}
        return cls(
            id=request.id,
            conversation_id=request.conversation_id,
            customer_id=request.customer_id,
            customer_name=customer_name,
            status=request.status,
            booking_status=details.get("booking_status"),
            check_in_date=details.get("check_in_date"),
            num_nights=details.get("num_nights"),
            adults=details.get("adults"),
            room_category=details.get("room_category"),
            staff_notes=details.get("staff_notes"),
            created_by=request.created_by,
            assigned_agent_id=request.assigned_agent_id,
            created_at=request.created_at,
            updated_at=request.updated_at,
        )


class BookingRequestUpdateRequest(BaseModel):
    status: str | None = None
    booking_status: str | None = None
    staff_notes: str | None = Field(default=None, max_length=2000)
    assigned_agent_id: uuid.UUID | None = None

    @field_validator("status")
    @classmethod
    def _v_status(cls, value: str | None) -> str | None:
        if value is not None and value not in SERVICE_REQUEST_STATUSES:
            raise ValueError(f"status must be one of {SERVICE_REQUEST_STATUSES}")
        return value

    @field_validator("booking_status")
    @classmethod
    def _v_booking_status(cls, value: str | None) -> str | None:
        if value is not None and value not in BOOKING_STATUSES:
            raise ValueError(f"booking_status must be one of {BOOKING_STATUSES}")
        return value
