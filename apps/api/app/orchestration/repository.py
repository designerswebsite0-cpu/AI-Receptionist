import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.orchestration.models import OrchestrationTurn, ServiceRequest

# --- orchestration_turns -------------------------------------------------------


async def get_turn(db: AsyncSession, turn_id: uuid.UUID) -> OrchestrationTurn | None:
    result = await db.execute(select(OrchestrationTurn).where(OrchestrationTurn.id == turn_id))
    return result.scalar_one_or_none()


async def list_turns_for_conversation(
    db: AsyncSession, conversation_id: uuid.UUID, *, limit: int = 50
) -> list[OrchestrationTurn]:
    result = await db.execute(
        select(OrchestrationTurn)
        .where(OrchestrationTurn.conversation_id == conversation_id)
        .order_by(OrchestrationTurn.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_turn_by_message_id(db: AsyncSession, message_id: uuid.UUID) -> OrchestrationTurn | None:
    """Idempotency lookup — app.orchestration.pipeline uses this to detect
    a retried/redelivered inbound message and replay its previously
    computed outcome instead of re-running the pipeline (and its tool/
    handoff side effects) a second time."""
    result = await db.execute(select(OrchestrationTurn).where(OrchestrationTurn.message_id == message_id))
    return result.scalar_one_or_none()


# --- service_requests -----------------------------------------------------------


async def get_service_request(db: AsyncSession, request_id: uuid.UUID) -> ServiceRequest | None:
    result = await db.execute(select(ServiceRequest).where(ServiceRequest.id == request_id))
    return result.scalar_one_or_none()


async def list_service_requests_for_conversation(db: AsyncSession, conversation_id: uuid.UUID) -> list[ServiceRequest]:
    result = await db.execute(
        select(ServiceRequest)
        .where(ServiceRequest.conversation_id == conversation_id)
        .order_by(ServiceRequest.created_at.desc())
    )
    return list(result.scalars().all())
