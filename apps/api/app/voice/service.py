"""Phase 9 inbound voice — business logic. Deliberately thin, mirroring
app.webchat.service's own precedent: a call is just another channel that
creates a Conversation (channel='voice') and Messages the same way webchat
does, then hands off to the one shared app.orchestration.pipeline.orchestrate()
— no second AI/business-logic implementation for voice. VoiceCall only
tracks call-specific metadata that doesn't belong on Conversation/Message.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.conversations import service as conversations_service
from app.conversations.models import Conversation
from app.conversations.schemas import ConversationCreateRequest
from app.customers import repository as customers_repository
from app.customers import service as customers_service
from app.customers.schemas import ContactIn, CustomerCreateRequest
from app.errors import NotFoundError, ValidationErrorApp
from app.orchestration.flow import engine as flow_engine
from app.voice import livekit_client, repository
from app.voice.models import VoiceCall


async def _find_or_create_caller(db: AsyncSession, *, phone: str):
    existing = await customers_repository.find_customer_by_contact(db, "phone", phone)
    if existing is not None:
        return existing
    return await customers_service.create_customer(
        db,
        body=CustomerCreateRequest(
            contacts=[ContactIn(contact_type="phone", value=phone, is_primary=True, verified=True)]
        ),
        actor_user_id=None,
    )


async def handle_incoming_call(
    db: AsyncSession, *, from_number: str, to_number: str, twilio_call_sid: str
) -> tuple[Conversation, VoiceCall]:
    """Called from the Twilio status-callback webhook the moment a call
    starts ringing — creates the Conversation+VoiceCall pair up front so
    the dashboard's Active Calls view can show it immediately, before the
    LiveKit agent has even joined."""
    existing = await repository.get_call_by_twilio_sid(db, twilio_call_sid)
    if existing is not None:
        conversation = await conversations_service.get_conversation_or_404(db, existing.conversation_id)
        return conversation, existing

    customer = await _find_or_create_caller(db, phone=from_number)
    conversation = await conversations_service.create_conversation(
        db, body=ConversationCreateRequest(customer_id=customer.id, channel="voice"), actor_user_id=None
    )

    call = VoiceCall(
        conversation_id=conversation.id,
        twilio_call_sid=twilio_call_sid,
        from_number=from_number,
        to_number=to_number,
        direction="inbound",
        status="ringing",
        started_at=datetime.now(UTC),
    )
    call = await repository.create_call(db, call=call)
    await db.commit()
    await db.refresh(call)
    return conversation, call


async def mark_call_status(
    db: AsyncSession, *, twilio_call_sid: str, status: str, livekit_room_name: str | None = None
) -> VoiceCall | None:
    call = await repository.get_call_by_twilio_sid(db, twilio_call_sid)
    if call is None:
        return None

    call.status = status
    if livekit_room_name:
        call.livekit_room_name = livekit_room_name
    if status in ("completed", "failed", "no_answer") and call.ended_at is None:
        call.ended_at = datetime.now(UTC)
        call.duration_seconds = repository.compute_duration_seconds(call.started_at, call.ended_at)
        if call.outcome is None:
            call.outcome = "failed" if status == "failed" else "abandoned" if status == "no_answer" else "ai_handled"

    await db.commit()
    await db.refresh(call)
    return call


async def get_call_or_404(db: AsyncSession, call_id: uuid.UUID) -> VoiceCall:
    call = await repository.get_call(db, call_id)
    if call is None:
        raise NotFoundError("Voice call not found")
    return call


async def takeover_call(db: AsyncSession, *, call_id: uuid.UUID, actor_user_id: uuid.UUID, staff_name: str | None):
    """Reuses the exact same handoff primitives as
    app.orchestration.router.force_handoff (conversations_service.
    change_status -> ai_active False) so the LiveKit agent's llm_node,
    which checks conversation.ai_active before every turn exactly like
    orchestrate() already does for text channels, goes silent — then mints
    a LiveKit token so the staff member's browser can join the same room
    and speak directly."""
    call = await get_call_or_404(db, call_id)
    conversation = await conversations_service.get_conversation_or_404(db, call.conversation_id)

    new_state, new_flow_state = flow_engine.apply_handoff(active=False)
    await conversations_service.change_dialogue_state(
        db,
        conversation_id=conversation.id,
        new_state=new_state,
        changed_by="human",
        metadata={"flow_state": new_flow_state, "reason": "voice_call_takeover", "forced_by": str(actor_user_id)},
        actor_user_id=actor_user_id,
    )
    conversation.flow_state = new_flow_state
    await conversations_service.change_status(
        db, conversation_id=conversation.id, new_status="escalated", actor_user_id=actor_user_id
    )
    call.outcome = "escalated"
    await db.commit()

    token = None
    if call.livekit_room_name:
        token = livekit_client.mint_staff_token(
            room_name=call.livekit_room_name, staff_user_id=str(actor_user_id), staff_name=staff_name
        )
    return call, token


async def end_call(db: AsyncSession, *, call_id: uuid.UUID) -> VoiceCall:
    call = await get_call_or_404(db, call_id)
    if call.status in ("completed", "failed", "no_answer"):
        raise ValidationErrorApp(f"Call is already '{call.status}'")

    if call.livekit_room_name:
        await livekit_client.end_room(call.livekit_room_name)

    call.status = "completed"
    call.ended_at = datetime.now(UTC)
    call.duration_seconds = repository.compute_duration_seconds(call.started_at, call.ended_at)
    if call.outcome is None:
        call.outcome = "staff_handled"

    await db.commit()
    await db.refresh(call)
    return call
