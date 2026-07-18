import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_audit_event
from app.orchestration.models import OrchestrationTurn, ServiceRequest


async def create_service_request(
    db: AsyncSession,
    *,
    conversation_id: uuid.UUID,
    customer_id: uuid.UUID,
    request_type: str,
    details: dict,
    created_by: str,
    actor_user_id: uuid.UUID | None,
) -> ServiceRequest:
    """The generic 'safe enquiry, not a fake completed operation' record
    every create_*_enquiry tool writes into — see
    docs/phase-4/PHASE_4_IMPLEMENTATION_PLAN.md §2. Never claims a
    booking/payment/refund succeeded; this is staff-facing intake only."""
    request = ServiceRequest(
        conversation_id=conversation_id,
        customer_id=customer_id,
        request_type=request_type,
        details=details,
        created_by=created_by,
    )
    db.add(request)
    await db.flush()

    await record_audit_event(
        db,
        actor_user_id=actor_user_id,
        action="service_request.created",
        resource_type="service_request",
        resource_id=str(request.id),
        after_state={"request_type": request_type, "created_by": created_by},
        metadata={"conversation_id": str(conversation_id)},
    )
    await db.commit()
    await db.refresh(request)
    return request


async def save_orchestration_turn(db: AsyncSession, turn: OrchestrationTurn) -> OrchestrationTurn:
    """Persists the decision trace for one pipeline run. Callers build the
    OrchestrationTurn object themselves (app.orchestration.pipeline) since
    its many fields are populated incrementally as the pipeline runs;
    this function's job is only the actual write + timestamp."""
    if turn.created_at is None:
        turn.created_at = datetime.now(UTC)
    db.add(turn)
    await db.commit()
    await db.refresh(turn)
    return turn
