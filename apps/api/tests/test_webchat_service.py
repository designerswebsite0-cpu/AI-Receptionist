"""Integration tests for app.webchat.service — the public webchat channel's
business logic. Same conventions as test_orchestration_pipeline.py: a real
Postgres via the schema-sandboxed db_session fixture, MockLLMProvider (never
a network call) + Phase 3's own no-network embedding/reranker fixtures.
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog
from app.config import get_settings
from app.conversations import service as conversations_service
from app.customers import repository as customers_repository
from app.customers import service as customers_service
from app.customers.schemas import ContactIn, CustomerCreateRequest
from app.knowledge.embeddings import MockEmbeddingProvider
from app.knowledge.retrieval.reranker import HeuristicReranker
from app.orchestration.llm.base import LLMResult
from app.orchestration.llm.mock_provider import MockLLMProvider
from app.webchat import repository as webchat_repository
from app.webchat import service as webchat_service

_EMBEDDING_PROVIDER = MockEmbeddingProvider()
_RERANKER = HeuristicReranker()
_SETTINGS = get_settings()


async def _new_session(db: AsyncSession):
    return await webchat_service.start_session(db, settings=_SETTINGS)


@pytest.mark.asyncio
async def test_start_session_creates_anonymous_customer_and_conversation(db_session: AsyncSession):
    result = await _new_session(db_session)

    assert result.token is not None and len(result.token) > 20
    assert result.current_state == "greeting"
    assert result.status == "open"
    assert result.ai_active is True
    assert result.human_active is False

    conversation = await conversations_service.get_conversation_or_404(db_session, result.conversation_id)
    assert conversation.channel == "webchat"

    session_row = await webchat_repository.get_by_id(db_session, result.session_id)
    customer = await customers_repository.get_customer(db_session, session_row.customer_id)
    assert customer is not None
    assert customer.full_name is None  # anonymous — no contact captured yet


@pytest.mark.asyncio
async def test_two_sessions_never_share_a_token_hash(db_session: AsyncSession):
    first = await _new_session(db_session)
    second = await _new_session(db_session)

    first_row = await webchat_repository.get_by_id(db_session, first.session_id)
    second_row = await webchat_repository.get_by_id(db_session, second.session_id)
    assert first_row.token_hash != second_row.token_hash

    # Resolving by one session's token must never return the other's row —
    # this is the actual IDOR-prevention property (app.webchat.deps relies
    # on this lookup being exact).
    resolved = await webchat_repository.get_by_token_hash(db_session, first_row.token_hash)
    assert resolved.id == first.session_id
    assert resolved.id != second.session_id


@pytest.mark.asyncio
async def test_get_session_state_never_returns_the_raw_token_again(db_session: AsyncSession):
    created = await _new_session(db_session)
    session_row = await webchat_repository.get_by_id(db_session, created.session_id)

    state = await webchat_service.get_session_state(db_session, session=session_row)
    assert state.token is None


@pytest.mark.asyncio
async def test_send_message_runs_orchestration_and_returns_guest_safe_response(db_session: AsyncSession):
    created = await _new_session(db_session)
    session_row = await webchat_repository.get_by_id(db_session, created.session_id)
    provider = MockLLMProvider(
        responses=[LLMResult(text="Check-in begins at 2:00 PM.", provider="mock", model="mock-llm", latency_ms=5)]
    )

    result = await webchat_service.send_message(
        db_session,
        session=session_row,
        text="What time is check-in?",
        client_message_id=None,
        llm_provider=provider,
        embedding_provider=_EMBEDDING_PROVIDER,
        reranker=_RERANKER,
    )

    assert result.response_text == "Check-in begins at 2:00 PM."
    assert result.handoff.required is False
    assert result.handoff.status == "none"
    assert result.ai_active is True
    # Guest-safe citation shape never carries internal identifiers.
    for citation in result.citations:
        assert not hasattr(citation, "chunk_id")
        assert not hasattr(citation, "score")


@pytest.mark.asyncio
async def test_send_message_with_same_client_message_id_does_not_call_the_llm_twice(db_session: AsyncSession):
    created = await _new_session(db_session)
    session_row = await webchat_repository.get_by_id(db_session, created.session_id)
    provider = MockLLMProvider(
        responses=[LLMResult(text="Only once.", provider="mock", model="mock-llm", latency_ms=5)]
    )
    client_message_id = str(uuid.uuid4())

    first = await webchat_service.send_message(
        db_session,
        session=session_row,
        text="Do you have a spa?",
        client_message_id=client_message_id,
        llm_provider=provider,
        embedding_provider=_EMBEDDING_PROVIDER,
        reranker=_RERANKER,
    )
    calls_after_first = provider.call_count
    assert calls_after_first > 0

    second = await webchat_service.send_message(
        db_session,
        session=session_row,
        text="Do you have a spa?",
        client_message_id=client_message_id,
        llm_provider=provider,
        embedding_provider=_EMBEDDING_PROVIDER,
        reranker=_RERANKER,
    )

    assert provider.call_count == calls_after_first, "duplicate submission must not re-invoke the LLM"
    assert second.response_text == first.response_text


@pytest.mark.asyncio
async def test_request_handoff_escalates_the_conversation(db_session: AsyncSession):
    created = await _new_session(db_session)
    session_row = await webchat_repository.get_by_id(db_session, created.session_id)

    result = await webchat_service.request_handoff(db_session, session=session_row, reason="Please connect me to staff")

    assert result.status == "escalated"
    assert result.current_state == "escalation"
    conversation = await conversations_service.get_conversation_or_404(db_session, session_row.conversation_id)
    assert conversation.flow_state == "human_handoff_requested"


@pytest.mark.asyncio
async def test_capture_contact_adds_a_new_contact_to_the_anonymous_customer(db_session: AsyncSession):
    created = await _new_session(db_session)
    session_row = await webchat_repository.get_by_id(db_session, created.session_id)

    await webchat_service.capture_contact(
        db_session,
        session=session_row,
        phone="+91 90000 11111",
        email=None,
        full_name="Asha Guest",
        marketing_consent=True,
    )

    customer = await customers_repository.get_customer(db_session, session_row.customer_id)
    assert customer.full_name == "Asha Guest"
    assert customer.preferences.get("marketing_consent") is True
    contacts = await customers_repository.list_contacts(db_session, session_row.customer_id)
    assert any(c.contact_type == "phone" and c.value == "+91 90000 11111" for c in contacts)


@pytest.mark.asyncio
async def test_capture_contact_repoints_conversation_to_a_pre_existing_customer_without_duplicating(
    db_session: AsyncSession,
):
    existing_customer = await customers_service.create_customer(
        db_session,
        body=CustomerCreateRequest(
            full_name="Returning Guest", contacts=[ContactIn(contact_type="phone", value="+91 90000 22222")]
        ),
        actor_user_id=None,
    )

    created = await _new_session(db_session)
    session_row = await webchat_repository.get_by_id(db_session, created.session_id)
    anonymous_customer_id = session_row.customer_id
    assert anonymous_customer_id != existing_customer.id

    await webchat_service.capture_contact(
        db_session,
        session=session_row,
        phone="+91 90000 22222",
        email=None,
        full_name=None,
        marketing_consent=False,
    )

    conversation = await conversations_service.get_conversation_or_404(db_session, session_row.conversation_id)
    assert conversation.customer_id == existing_customer.id
    assert session_row.customer_id == existing_customer.id

    contacts = await customers_repository.list_contacts(db_session, existing_customer.id)
    matching = [c for c in contacts if c.value == "+91 90000 22222"]
    assert len(matching) == 1, "must not create a duplicate contact/customer for an already-known guest"


@pytest.mark.asyncio
async def test_submit_feedback_writes_an_audit_event(db_session: AsyncSession):
    created = await _new_session(db_session)
    session_row = await webchat_repository.get_by_id(db_session, created.session_id)

    await webchat_service.submit_feedback(db_session, session=session_row, turn_id=None, rating="up", comment="Great!")

    result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "webchat.feedback_submitted")
    )
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].event_metadata["rating"] == "up"


@pytest.mark.asyncio
async def test_end_session_revokes_it(db_session: AsyncSession):
    created = await _new_session(db_session)
    session_row = await webchat_repository.get_by_id(db_session, created.session_id)

    await webchat_service.end_session(db_session, session=session_row)

    refreshed = await webchat_repository.get_by_id(db_session, created.session_id)
    assert refreshed.revoked_at is not None
