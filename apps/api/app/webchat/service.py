"""Business logic for the public webchat channel. Deliberately thin: guest
message handling persists a Message the same way any other channel would,
then calls app.orchestration.pipeline.orchestrate() — the one pipeline
every channel shares. No second AI/business-logic implementation lives
here (Phase 5 brief: "Do not create a second AI orchestration
implementation inside the website.").
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_audit_event
from app.config import Settings
from app.conversations import service as conversations_service
from app.conversations.models import Conversation
from app.conversations.schemas import ConversationCreateRequest
from app.customers import repository as customers_repository
from app.customers import service as customers_service
from app.customers.schemas import ContactIn, CustomerCreateRequest, CustomerUpdateRequest
from app.errors import ConflictError
from app.feedback import service as feedback_service
from app.knowledge.embeddings import EmbeddingProvider
from app.knowledge.retrieval.reranker import Reranker
from app.messages import repository as messages_repository
from app.messages import service as messages_service
from app.messages.schemas import MessageCreateRequest
from app.orchestration import repository as orch_repository
from app.orchestration.domain import OrchestrationResult
from app.orchestration.flow import engine as flow_engine
from app.orchestration.llm.base import LLMProvider
from app.orchestration.pipeline import orchestrate
from app.webchat import repository as webchat_repository
from app.webchat.models import WebchatSession
from app.webchat.schemas import (
    WebchatCitationOut,
    WebchatHandoffOut,
    WebchatMessageOut,
    WebchatSessionOut,
)


def _session_out(session: WebchatSession, conversation: Conversation, *, token: str | None) -> WebchatSessionOut:
    return WebchatSessionOut(
        session_id=session.id,
        conversation_id=conversation.id,
        token=token,
        expires_at=session.expires_at,
        current_state=conversation.current_state,
        flow_state=conversation.flow_state,
        status=conversation.status,
        ai_active=conversation.ai_active,
        human_active=conversation.human_active,
    )


async def start_session(db: AsyncSession, *, settings: Settings) -> WebchatSessionOut:
    customer = await customers_service.create_customer(
        db, body=CustomerCreateRequest(preferred_channel="webchat"), actor_user_id=None
    )
    conversation = await conversations_service.create_conversation(
        db, body=ConversationCreateRequest(customer_id=customer.id, channel="webchat"), actor_user_id=None
    )

    raw_token = webchat_repository.generate_token()
    expires_at = datetime.now(UTC) + timedelta(seconds=settings.webchat_session_ttl_seconds)
    session = await webchat_repository.create_session(
        db,
        customer_id=customer.id,
        conversation_id=conversation.id,
        token_hash=webchat_repository.hash_token(raw_token),
        expires_at=expires_at,
    )
    await db.commit()
    await db.refresh(session)
    return _session_out(session, conversation, token=raw_token)


async def get_session_state(db: AsyncSession, *, session: WebchatSession) -> WebchatSessionOut:
    conversation = await conversations_service.get_conversation_or_404(db, session.conversation_id)
    return _session_out(session, conversation, token=None)


async def list_transcript(
    db: AsyncSession, *, session: WebchatSession, offset: int, limit: int
) -> tuple[list, int]:
    return await messages_repository.list_messages(db, session.conversation_id, offset=offset, limit=limit)


def _handoff_status(conversation: Conversation, handoff_required: bool) -> str:
    if conversation.human_active:
        return "active"
    if handoff_required or conversation.flow_state in ("human_handoff_requested", "human_handoff_active"):
        return "requested"
    return "none"


async def _build_message_out(
    db: AsyncSession, *, conversation: Conversation, message_id: uuid.UUID, result: OrchestrationResult
) -> WebchatMessageOut:
    turn = await orch_repository.get_turn_by_message_id(db, message_id)
    citations = []
    response_message_id = None
    if turn is not None:
        response_message_id = turn.response_message_id
        citations = [
            WebchatCitationOut(
                source_title=c["source_title"],
                source_priority=c["source_priority"],
                authoritative=c["authoritative"],
            )
            for c in (turn.citations or [])
        ]

    return WebchatMessageOut(
        message_id=response_message_id,
        response_text=result.response_text,
        citations=citations,
        handoff=WebchatHandoffOut(
            required=result.handoff_decision.required,
            status=_handoff_status(conversation, result.handoff_decision.required),
            department=result.handoff_decision.department,
        ),
        ai_active=conversation.ai_active,
        human_active=conversation.human_active,
        flow_state=result.flow_state,
        error_code=result.error_code,
    )


async def send_message(
    db: AsyncSession,
    *,
    session: WebchatSession,
    text: str,
    client_message_id: str | None,
    llm_provider: LLMProvider,
    embedding_provider: EmbeddingProvider,
    reranker: Reranker,
    background_tasks: BackgroundTasks | None = None,
) -> WebchatMessageOut:
    # Duplicate-submission guard (brief §11/§12: "Prevent duplicate sends
    # from rapid clicks"): reuses the same idempotency primitive Phase 6
    # WhatsApp webhooks are designed around (Message.external_message_id +
    # messages_repository.find_by_external_id), rather than inventing a
    # second dedup mechanism.
    external_id = f"webchat:{client_message_id}" if client_message_id else None
    message = await messages_repository.find_by_external_id(db, external_id) if external_id else None
    if message is None:
        message = await messages_service.send_message(
            db,
            conversation_id=session.conversation_id,
            body=MessageCreateRequest(sender_type="customer", content_text=text, external_message_id=external_id),
            actor_user_id=None,
        )

    result = await orchestrate(
        db,
        conversation_id=session.conversation_id,
        message_id=message.id,
        guest_message=text,
        channel="webchat",
        llm_provider=llm_provider,
        embedding_provider=embedding_provider,
        reranker=reranker,
        actor_user_id=None,
        background_tasks=background_tasks,
    )

    conversation = await conversations_service.get_conversation_or_404(db, session.conversation_id)
    return await _build_message_out(db, conversation=conversation, message_id=message.id, result=result)


async def request_handoff(db: AsyncSession, *, session: WebchatSession, reason: str) -> WebchatSessionOut:
    """Guest-initiated escalation (e.g. the "Speak to staff" quick action).
    Reuses the exact same deterministic primitives the staff-facing forced
    handoff already uses (app.orchestration.router.force_handoff) rather
    than a second implementation — only `changed_by` differs, since a guest
    is neither "ai" nor "human" staff in app.conversations.constants.
    STATE_CHANGED_BY's vocabulary ("system" is the correct bucket)."""
    conversation = await conversations_service.get_conversation_or_404(db, session.conversation_id)
    new_state, new_flow_state = flow_engine.apply_handoff(active=False)

    await conversations_service.change_dialogue_state(
        db,
        conversation_id=session.conversation_id,
        new_state=new_state,
        changed_by="system",
        metadata={"flow_state": new_flow_state, "reason": reason, "requested_by": "guest"},
        actor_user_id=None,
    )
    conversation.flow_state = new_flow_state
    await conversations_service.change_status(
        db, conversation_id=session.conversation_id, new_status="escalated", actor_user_id=None
    )
    await db.refresh(conversation)
    return _session_out(session, conversation, token=None)


async def submit_feedback(
    db: AsyncSession, *, session: WebchatSession, turn_id: uuid.UUID | None, rating: str, comment: str | None
) -> None:
    await record_audit_event(
        db,
        actor_user_id=None,
        action="webchat.feedback_submitted",
        resource_type="orchestration_turn" if turn_id else "conversation",
        resource_id=str(turn_id or session.conversation_id),
        metadata={"rating": rating, "comment": comment, "conversation_id": str(session.conversation_id)},
    )
    await db.commit()

    # Additive: the audit-log write above is untouched (already-working
    # behavior) — this also inserts one structured row so the guest's
    # thumbs-up/down surfaces as a real Customer Feedback dashboard item
    # (Phase X Stage 7) instead of only being visible by grepping audit logs.
    await feedback_service.record_webchat_feedback(
        db,
        rating=rating,
        comment=comment,
        conversation_id=session.conversation_id,
        customer_id=session.customer_id,
        turn_id=turn_id,
    )


async def capture_contact(
    db: AsyncSession,
    *,
    session: WebchatSession,
    phone: str | None,
    email: str | None,
    full_name: str | None,
    marketing_consent: bool,
) -> None:
    """Reuses the existing Customer 360 contact model — never confirms or
    denies to the caller whether a value already belonged to someone else
    (brief §8). When it does, this conversation (and session) is re-pointed
    to that pre-existing identity instead of creating a duplicate customer,
    which is the correct Customer 360 outcome either way, so the guest-
    visible response is identical in both branches (see router)."""
    target_customer_id = session.customer_id
    for contact_type, value in (("phone", phone), ("email", email)):
        if not value:
            continue
        existing = await customers_repository.find_customer_by_contact(db, contact_type, value)
        if existing is not None and existing.id != session.customer_id:
            target_customer_id = existing.id
            continue
        try:
            await customers_service.add_contact(
                db,
                customer_id=session.customer_id,
                body=ContactIn(contact_type=contact_type, value=value, is_primary=True, verified=False),
                actor_user_id=None,
            )
        except ConflictError:
            existing = await customers_repository.find_customer_by_contact(db, contact_type, value)
            if existing is not None:
                target_customer_id = existing.id

    if target_customer_id != session.customer_id:
        conversation = await conversations_service.get_conversation_or_404(db, session.conversation_id)
        conversation.customer_id = target_customer_id
        session.customer_id = target_customer_id

    customer = await customers_service.get_customer_or_404(db, target_customer_id)
    updates: dict = {}
    if full_name and not customer.full_name:
        updates["full_name"] = full_name
    if marketing_consent:
        preferences = dict(customer.preferences or {})
        preferences["marketing_consent"] = True
        preferences["marketing_consent_at"] = datetime.now(UTC).isoformat()
        updates["preferences"] = preferences
    if updates:
        await customers_service.update_customer(
            db, customer_id=target_customer_id, body=CustomerUpdateRequest(**updates), actor_user_id=None
        )

    await db.commit()


async def end_session(db: AsyncSession, *, session: WebchatSession) -> None:
    webchat_repository.revoke(session)
    await db.commit()


async def clear_all_sessions(db: AsyncSession, *, actor_user_id: uuid.UUID) -> int:
    """Staff-triggered only (dashboard button) — see
    app.webchat.repository.revoke_all_active's own docstring for exactly
    what this does and doesn't affect."""
    count = await webchat_repository.revoke_all_active(db)
    await record_audit_event(
        db,
        actor_user_id=actor_user_id,
        action="webchat.all_sessions_cleared",
        resource_type="webchat_session",
        metadata={"sessions_revoked": count},
    )
    await db.commit()
    return count
