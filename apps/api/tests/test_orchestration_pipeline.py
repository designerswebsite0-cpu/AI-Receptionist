"""Integration tests for app.orchestration.pipeline.orchestrate — the
top-level pipeline wiring every other orchestration module together.
Requires a reachable Postgres (see conftest.db_session); skips cleanly
when none is available. Uses MockLLMProvider (never a network call) and
MockEmbeddingProvider/HeuristicReranker (Phase 3's own no-network
fixtures) throughout — no paid API call in this suite, per this session's
testing discipline.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversations import service as conversation_service
from app.conversations.schemas import ConversationCreateRequest
from app.customers import service as customer_service
from app.customers.schemas import CustomerCreateRequest
from app.knowledge.embeddings import MockEmbeddingProvider
from app.knowledge.retrieval.reranker import HeuristicReranker
from app.messages import service as messages_service
from app.messages.schemas import MessageCreateRequest
from app.orchestration import repository as orch_repository
from app.orchestration.llm.base import LLMMessage, LLMResult, LLMToolCall
from app.orchestration.llm.mock_provider import MockLLMProvider
from app.orchestration.pipeline import orchestrate

_EMBEDDING_PROVIDER = MockEmbeddingProvider()
_RERANKER = HeuristicReranker()


async def _make_conversation(db: AsyncSession):
    customer = await customer_service.create_customer(
        db, body=CustomerCreateRequest(full_name="Jane Guest"), actor_user_id=None
    )
    conversation = await conversation_service.create_conversation(
        db, body=ConversationCreateRequest(customer_id=customer.id, channel="webchat"), actor_user_id=None
    )
    return customer, conversation


async def _send_guest_message(db: AsyncSession, conversation_id, text: str):
    return await messages_service.send_message(
        db,
        conversation_id=conversation_id,
        body=MessageCreateRequest(sender_type="customer", content_text=text),
        actor_user_id=None,
    )


@pytest.mark.asyncio
async def test_ordinary_question_gets_a_plain_text_response_and_no_handoff(db_session: AsyncSession):
    _, conversation = await _make_conversation(db_session)
    guest_message = await _send_guest_message(db_session, conversation.id, "What time is check-in?")

    provider = MockLLMProvider(
        responses=[LLMResult(text="Check-in begins at 2:00 PM.", provider="mock", model="mock-llm", latency_ms=5)]
    )
    result = await orchestrate(
        db_session,
        conversation_id=conversation.id,
        message_id=guest_message.id,
        guest_message="What time is check-in?",
        channel="webchat",
        llm_provider=provider,
        embedding_provider=_EMBEDDING_PROVIDER,
        reranker=_RERANKER,
    )

    assert result.response_text == "Check-in begins at 2:00 PM."
    assert result.handoff_decision.required is False
    assert result.validation_result.passed is True

    turn = await orch_repository.get_turn_by_message_id(db_session, guest_message.id)
    assert turn is not None
    assert turn.detected_intent == "general_checkin_checkout"


@pytest.mark.asyncio
async def test_replaying_the_same_message_id_does_not_call_the_llm_again(db_session: AsyncSession):
    _, conversation = await _make_conversation(db_session)
    guest_message = await _send_guest_message(db_session, conversation.id, "What time is check-in?")

    provider = MockLLMProvider(
        responses=[LLMResult(text="Check-in begins at 2:00 PM.", provider="mock", model="mock-llm", latency_ms=5)]
    )
    await orchestrate(
        db_session,
        conversation_id=conversation.id,
        message_id=guest_message.id,
        guest_message="What time is check-in?",
        channel="webchat",
        llm_provider=provider,
        embedding_provider=_EMBEDDING_PROVIDER,
        reranker=_RERANKER,
    )
    calls_after_first_run = provider.call_count
    assert calls_after_first_run > 0

    replay_result = await orchestrate(
        db_session,
        conversation_id=conversation.id,
        message_id=guest_message.id,
        guest_message="What time is check-in?",
        channel="webchat",
        llm_provider=provider,
        embedding_provider=_EMBEDDING_PROVIDER,
        reranker=_RERANKER,
    )

    assert provider.call_count == calls_after_first_run, "replay must not re-invoke the LLM"
    assert replay_result.response_text == "Check-in begins at 2:00 PM."


@pytest.mark.asyncio
async def test_small_talk_message_skips_llm_entity_extraction(db_session: AsyncSession):
    _, conversation = await _make_conversation(db_session)
    guest_message = await _send_guest_message(db_session, conversation.id, "Hi")

    provider = MockLLMProvider(
        responses=[
            LLMResult(text="Hello! How can I help you today?", provider="mock", model="mock-llm", latency_ms=5)
        ]
    )
    result = await orchestrate(
        db_session,
        conversation_id=conversation.id,
        message_id=guest_message.id,
        guest_message="Hi",
        channel="webchat",
        llm_provider=provider,
        embedding_provider=_EMBEDDING_PROVIDER,
        reranker=_RERANKER,
    )

    assert result.response_text == "Hello! How can I help you today?"
    # Small talk is classified deterministically (no LLM call) and never
    # carries a semantic entity (room category, dietary restriction, etc.),
    # so the LLM entity-extraction call is skipped too — only the main
    # generation call should have run.
    assert provider.call_count == 1


@pytest.mark.asyncio
async def test_earlier_stated_entities_are_recalled_on_a_later_turn_without_repeating_them(
    db_session: AsyncSession,
):
    """Regression test for a real reported bug: a guest gives their dates
    and party size, then a later message ("what's the final price?")
    doesn't repeat them — the AI must still know them, not ask again.
    """
    _, conversation = await _make_conversation(db_session)

    first_message = await _send_guest_message(
        db_session,
        conversation.id,
        "I'd like to book a room, check-in 15 August 2026, check-out 20 August 2026, 2 adults.",
    )
    await orchestrate(
        db_session,
        conversation_id=conversation.id,
        message_id=first_message.id,
        guest_message=first_message.content_text,
        channel="webchat",
        llm_provider=MockLLMProvider(
            responses=[LLMResult(text="Sure, let me pull that up.", provider="mock", model="mock-llm", latency_ms=5)]
        ),
        embedding_provider=_EMBEDDING_PROVIDER,
        reranker=_RERANKER,
    )

    captured_messages: list[LLMMessage] = []

    def _capture(messages: list[LLMMessage]) -> LLMResult:
        captured_messages.extend(messages)
        return LLMResult(text="The rate for that stay is INR 12,500.", provider="mock", model="mock-llm", latency_ms=5)

    second_message = await _send_guest_message(
        db_session, conversation.id, "What's the final price for the Garden Deluxe Room?"
    )
    await orchestrate(
        db_session,
        conversation_id=conversation.id,
        message_id=second_message.id,
        guest_message=second_message.content_text,
        channel="webchat",
        llm_provider=MockLLMProvider(responder=_capture),
        embedding_provider=_EMBEDDING_PROVIDER,
        reranker=_RERANKER,
    )

    final_user_message = captured_messages[-1].content
    assert "ALREADY STATED THIS CONVERSATION" in final_user_message
    assert "check_in_date" in final_user_message
    assert "15 August 2026" in final_user_message


@pytest.mark.asyncio
async def test_mandatory_handoff_intent_skips_generation_and_escalates_the_conversation(db_session: AsyncSession):
    _, conversation = await _make_conversation(db_session)
    guest_message = await _send_guest_message(db_session, conversation.id, "I want a refund for my stay")

    provider = MockLLMProvider()
    result = await orchestrate(
        db_session,
        conversation_id=conversation.id,
        message_id=guest_message.id,
        guest_message="I want a refund for my stay",
        channel="webchat",
        llm_provider=provider,
        embedding_provider=_EMBEDDING_PROVIDER,
        reranker=_RERANKER,
    )

    assert result.handoff_decision.required is True
    assert result.handoff_decision.reason_code == "refund_request"
    assert result.handoff_decision.department == "billing"
    # entity extraction still runs (always calls when a provider is given);
    # the generation call itself must be skipped for a mandatory handoff.
    assert provider.call_count == 1

    await db_session.refresh(conversation)
    assert conversation.status == "escalated"
    assert conversation.current_state == "escalation"
    assert conversation.flow_state == "human_handoff_requested"


@pytest.mark.asyncio
async def test_tool_call_executes_and_the_followup_response_reflects_the_tool_result(db_session: AsyncSession):
    _, conversation = await _make_conversation(db_session)
    guest_message = await _send_guest_message(
        db_session, conversation.id, "Book a room for 2 adults, check in 15 July, 3 nights"
    )

    def _responder(messages: list[LLMMessage]) -> LLMResult:
        if any(m.role == "tool" for m in messages):
            return LLMResult(
                text="Great, I've recorded your booking enquiry — our team will confirm shortly.",
                provider="mock", model="mock-llm", latency_ms=5,
            )
        return LLMResult(
            text="Let me record that enquiry for you.", provider="mock", model="mock-llm", latency_ms=5,
            tool_calls=[
                LLMToolCall(
                    call_id="call_1", tool_name="create_booking_enquiry", arguments={"check_in_date": "15 July 2026"}
                )
            ],
        )

    provider = MockLLMProvider(responder=_responder)
    result = await orchestrate(
        db_session,
        conversation_id=conversation.id,
        message_id=guest_message.id,
        guest_message="Book a room for 2 adults, check in 15 July, 3 nights",
        channel="webchat",
        llm_provider=provider,
        embedding_provider=_EMBEDDING_PROVIDER,
        reranker=_RERANKER,
    )

    assert result.tool_decision.status == "success"
    assert result.tool_decision.tool_name == "create_booking_enquiry"
    assert "recorded" in result.response_text.lower()
    # never a fake "booking confirmed" claim from the tool result itself
    assert "confirmed" not in result.tool_decision.output.get("status", "")


@pytest.mark.asyncio
async def test_search_resort_knowledge_tool_call_is_handled_by_the_pipeline_itself(db_session: AsyncSession):
    """Real bug found via the Phase 4 real-data validation checklist run
    against real OpenAI + the real RKPR corpus: search_resort_knowledge is
    registered so the model can request a follow-up lookup, but
    tools.handlers explicitly does NOT implement it (by design — see its
    own docstring) since it needs the embedding provider/reranker the
    pipeline holds, not tools.handlers. Before this fix, every real call to
    this tool fell through to tools.handlers.execute_tool's ValueError,
    caught by the pipeline's broad except, producing the generic
    "I ran into an issue completing that" fallback instead of an answer —
    3 of 13 real messages failed this way until this was implemented.
    """
    _, conversation = await _make_conversation(db_session)
    guest_message = await _send_guest_message(db_session, conversation.id, "What's the difference between rooms?")

    def _responder(messages: list[LLMMessage]) -> LLMResult:
        if any(m.role == "tool" for m in messages):
            return LLMResult(
                text="Here's a comparison based on what I found.", provider="mock", model="mock-llm", latency_ms=5
            )
        return LLMResult(
            text="Let me check on that.", provider="mock", model="mock-llm", latency_ms=5,
            tool_calls=[
                LLMToolCall(call_id="call_1", tool_name="search_resort_knowledge", arguments={"query": "room types"})
            ],
        )

    provider = MockLLMProvider(responder=_responder)
    result = await orchestrate(
        db_session,
        conversation_id=conversation.id,
        message_id=guest_message.id,
        guest_message="What's the difference between rooms?",
        channel="webchat",
        llm_provider=provider,
        embedding_provider=_EMBEDDING_PROVIDER,
        reranker=_RERANKER,
    )

    assert result.tool_decision.status == "success"
    assert result.tool_decision.tool_name == "search_resort_knowledge"
    assert result.response_text == "Here's a comparison based on what I found."
    assert "query" in result.tool_decision.output


@pytest.mark.asyncio
async def test_ai_locked_out_when_conversation_is_human_handled(db_session: AsyncSession):
    _, conversation = await _make_conversation(db_session)
    await conversation_service.change_status(
        db_session, conversation_id=conversation.id, new_status="human_handling", actor_user_id=None
    )
    guest_message = await _send_guest_message(db_session, conversation.id, "Are you still there?")

    provider = MockLLMProvider()
    result = await orchestrate(
        db_session,
        conversation_id=conversation.id,
        message_id=guest_message.id,
        guest_message="Are you still there?",
        channel="webchat",
        llm_provider=provider,
        embedding_provider=_EMBEDDING_PROVIDER,
        reranker=_RERANKER,
    )

    assert result.response_text is None
    assert result.error_code == "ai_locked_out"
    assert provider.call_count == 0


@pytest.mark.asyncio
async def test_unsafe_response_is_replaced_with_safe_fallback_and_triggers_handoff(db_session: AsyncSession):
    _, conversation = await _make_conversation(db_session)
    guest_message = await _send_guest_message(db_session, conversation.id, "What is the room price?")

    provider = MockLLMProvider(
        responses=[
            LLMResult(
                text="The room price is INR 25,000 per night.",  # no supporting citation -> guardrail blocks this
                provider="mock", model="mock-llm", latency_ms=5,
            )
        ]
    )
    result = await orchestrate(
        db_session,
        conversation_id=conversation.id,
        message_id=guest_message.id,
        guest_message="What is the room price?",
        channel="webchat",
        llm_provider=provider,
        embedding_provider=_EMBEDDING_PROVIDER,
        reranker=_RERANKER,
    )

    assert result.validation_result.blocked is True
    assert result.response_text != "The room price is INR 25,000 per night."
    assert "team" in result.response_text.lower()
    assert result.handoff_decision.required is True
    assert result.handoff_decision.reason_code == "retrieval_insufficient_for_sensitive_answer"
