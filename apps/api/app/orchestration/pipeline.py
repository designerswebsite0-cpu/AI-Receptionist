"""Top-level, channel-neutral orchestration pipeline — architecture.md
§4.4's 8-step pipeline (classify -> extract -> retrieve -> assemble ->
generate -> validate tools -> validate response -> persist), expanded to
the more granular sequence in docs/phase-4/PHASE_4_IMPLEMENTATION_PLAN.md
§7. `orchestrate()` is the single entry point every channel (webchat API,
WhatsApp webhook, future voice) calls with one already-persisted guest
message; nothing else wires steps 2-10 together, and none of those modules
know about each other directly.
"""

import asyncio
import json
import logging
import uuid

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.conversations import service as conversations_service
from app.customers.repository import get_customer
from app.database import AsyncSessionLocal
from app.knowledge.embeddings import EmbeddingProvider
from app.knowledge.retrieval import service as retrieval_service
from app.knowledge.retrieval.reranker import Reranker
from app.messages import repository as messages_repository
from app.messages import service as messages_service
from app.messages.schemas import MessageCreateRequest
from app.orchestration import memory
from app.orchestration import repository as orch_repository
from app.orchestration import service as orch_service
from app.orchestration.context.assembler import assemble_context
from app.orchestration.domain import (
    DetectedIntent,
    ExtractedEntities,
    HandoffDecision,
    MissingInformation,
    OrchestrationResult,
    ProviderUsage,
    RetrievedContext,
    ToolDecision,
    ValidationResult,
)
from app.orchestration.flow import engine as flow_engine
from app.orchestration.guardrails.validator import safe_fallback_response, validate_response
from app.orchestration.handoff.engine import evaluate_handoff_requirement
from app.orchestration.intent.classifier import classify_intent
from app.orchestration.intent.entities import extract_entities, validate_stay_dates
from app.orchestration.llm.base import LLMMessage, LLMProvider
from app.orchestration.llm.fallback import AllProvidersFailedError
from app.orchestration.models import OrchestrationTurn
from app.orchestration.prompts.builder import build_messages
from app.orchestration.tools import handlers as tool_handlers
from app.orchestration.tools.registry import to_openai_tools
from app.orchestration.tools.validation import validate_tool_call

logger = logging.getLogger(__name__)

# How many of the most recent turns to look at when counting a *consecutive*
# streak of low-confidence classifications or tool failures — matches
# app.orchestration.handoff.engine's own thresholds (3 and 2), so 5 is
# comfortably enough lookback without scanning the whole conversation.
_STREAK_LOOKBACK = 5
_LOW_CONFIDENCE_STREAK_THRESHOLD = 0.45  # mirrors intent.classifier._LLM_ESCALATION_THRESHOLD

_HANDOFF_ACKNOWLEDGMENT = (
    "I want to make sure this gets handled properly, so I'm connecting you with a member "
    "of our team now — they'll follow up with you shortly."
)
_TOOL_FAILURE_ACKNOWLEDGMENT = (
    "I ran into an issue completing that — let me connect you with a team member who can help."
)
_PROVIDER_FAILURE_ACKNOWLEDGMENT = (
    "I'm having trouble processing that right now — let me connect you with a team member."
)


def _count_consecutive(turns: list[OrchestrationTurn], predicate) -> int:
    """`turns` is ordered most-recent-first. Counts a run starting at the
    most recent turn; a single non-matching turn anywhere in between
    breaks the streak, since that's evidence things are back on track."""
    count = 0
    for turn in turns:
        if predicate(turn):
            count += 1
        else:
            break
    return count


def _is_low_confidence(turn: OrchestrationTurn) -> bool:
    return turn.intent_confidence is not None and turn.intent_confidence < _LOW_CONFIDENCE_STREAK_THRESHOLD


def _is_tool_failure(turn: OrchestrationTurn) -> bool:
    return turn.tool_status == "failed"


def _merge_with_recent_entities(
    entities: ExtractedEntities, recent_turns: list[OrchestrationTurn]
) -> ExtractedEntities:
    """A follow-up like "what's the final price?" rarely repeats the
    check-in date, guest count, or room category given a turn or two
    earlier — entity extraction only ever looks at the *current* message,
    so on its own it has no way to know those are still true. This
    backfills any field the current message didn't mention from the most
    recent past turn that did (recent_turns is most-recent-first, so the
    first match wins), which is what lets flow_engine's missing-info check
    and the prompt's stated-details block correctly remember earlier
    answers instead of asking the guest to repeat themselves. Never
    overwrites a field the guest just gave in this message — recency
    always favors what they're saying *right now*."""
    values = dict(entities.values)
    confidence = dict(entities.confidence)
    source = dict(entities.source)
    for turn in recent_turns:
        for field_name, value in (turn.extracted_entities or {}).items():
            if field_name not in values and value is not None:
                values[field_name] = value
                confidence[field_name] = 0.75
                source[field_name] = "conversation_history"
    return ExtractedEntities(values=values, confidence=confidence, source=source)


async def _search_resort_knowledge(
    db: AsyncSession,
    *,
    query: str,
    conversation_id: uuid.UUID,
    embedding_provider: EmbeddingProvider,
    reranker: Reranker,
) -> dict:
    """Executes the LLM's own requested follow-up lookup — a real query
    against the knowledge base, not a canned response. Guest-safety
    filtering (guest_only=True) applies exactly as it does for the initial
    context-assembly retrieval; this is a second, targeted search, not a
    way to bypass it."""
    search_response = await retrieval_service.search(
        db,
        query_text=query,
        embedding_provider=embedding_provider,
        reranker=reranker,
        guest_only=True,
        limit=5,
        conversation_id=conversation_id,
        requested_channel="orchestration_tool_call",
    )
    return {
        "query": query,
        "results": [
            {"source_title": c.source_title, "content": c.content, "source_priority": c.source_priority}
            for c in search_response.results
        ],
    }


async def _result_from_existing_turn(db: AsyncSession, turn: OrchestrationTurn) -> OrchestrationResult:
    """Replay path for a message_id already processed (webhook redelivery,
    client retry) — returns the previously computed outcome instead of
    running the pipeline (and therefore any tool/handoff side effects)
    a second time."""
    response_text = None
    if turn.response_message_id is not None:
        response_message = await messages_repository.get_message(db, turn.response_message_id)
        response_text = response_message.content_text if response_message else None

    return OrchestrationResult(
        conversation_id=turn.conversation_id,
        response_text=response_text,
        intent=DetectedIntent(
            primary_intent=turn.detected_intent or "unknown",
            confidence=turn.intent_confidence or 0.0,
            secondary_intents=[tuple(pair) for pair in turn.secondary_intents],
        ),
        entities=ExtractedEntities(values=turn.extracted_entities),
        missing_information=MissingInformation(required_fields=turn.missing_entities),
        retrieved_context=RetrievedContext(query=turn.retrieval_query or ""),
        flow_state=turn.flow_state,
        tool_decision=ToolDecision(
            tool_name=turn.tool_name,
            tool_input=turn.tool_input,
            decision="execute" if turn.tool_status == "success" else "none",
            output=turn.tool_output,
            status=turn.tool_status,
        ),
        handoff_decision=HandoffDecision(
            required=turn.handoff_required,
            priority=turn.handoff_priority or "normal",
            department=turn.handoff_department,
            reason_code=turn.handoff_reason,
        ),
        validation_result=ValidationResult(passed=not turn.validation_result.get("blocked", False)),
        provider_usage=(
            ProviderUsage(provider=turn.provider_used, model=turn.model_used or "", latency_ms=turn.latency_ms or 0)
            if turn.provider_used
            else None
        ),
        error_code=turn.error_code,
        error_message=turn.error_message,
        created_at=turn.created_at,
    )


async def _record_inferences_background(
    *, customer_id: uuid.UUID, entities: ExtractedEntities, conversation_id: uuid.UUID
) -> None:
    """Runs after the guest-facing reply has already been sent (scheduled
    via FastAPI's BackgroundTasks). Cannot reuse the request's AsyncSession
    — FastAPI's dependency exit stack has already closed it by the time a
    background task runs — so this opens its own short-lived session
    instead, mirroring app.database.get_db's own pattern."""
    try:
        async with AsyncSessionLocal() as db:
            customer = await get_customer(db, customer_id)
            if customer is not None:
                await memory.record_inferences(db, customer=customer, entities=entities, conversation_id=conversation_id)
    except Exception:  # noqa: BLE001 - background best-effort; must never affect a turn already replied to
        logger.exception("Background customer-inference write failed for conversation %s", conversation_id)


async def orchestrate(
    db: AsyncSession,
    *,
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    guest_message: str,
    channel: str,
    llm_provider: LLMProvider,
    embedding_provider: EmbeddingProvider,
    reranker: Reranker,
    actor_user_id: uuid.UUID | None = None,
    background_tasks: BackgroundTasks | None = None,
) -> OrchestrationResult:
    existing_turn = await orch_repository.get_turn_by_message_id(db, message_id)
    if existing_turn is not None:
        return await _result_from_existing_turn(db, existing_turn)

    conversation = await conversations_service.get_conversation_or_404(db, conversation_id)

    # Handoff lockout: once a human has actively taken over (ai_active is
    # flipped False by conversations.service.change_status), the AI must
    # never generate or send a reply into the same conversation — doing so
    # would race with, or contradict, whatever the staff member is saying.
    if not conversation.ai_active:
        turn = OrchestrationTurn(
            conversation_id=conversation_id,
            message_id=message_id,
            error_code="ai_locked_out",
            error_message="Conversation is currently handled by a human agent; AI response suppressed.",
        )
        await orch_service.save_orchestration_turn(db, turn)
        return OrchestrationResult(
            conversation_id=conversation_id,
            response_text=None,
            intent=DetectedIntent(primary_intent="unknown", confidence=0.0),
            entities=ExtractedEntities(),
            missing_information=MissingInformation(),
            retrieved_context=RetrievedContext(query=guest_message),
            flow_state=conversation.flow_state,
            tool_decision=ToolDecision(tool_name=None),
            handoff_decision=HandoffDecision(required=False),
            validation_result=ValidationResult(passed=True),
            provider_usage=None,
            error_code="ai_locked_out",
            error_message="Conversation is currently handled by a human agent; AI response suppressed.",
        )

    customer = await get_customer(db, conversation.customer_id)

    recent_turns = await orch_repository.list_turns_for_conversation(db, conversation_id, limit=_STREAK_LOOKBACK)
    consecutive_low_confidence = _count_consecutive(recent_turns, _is_low_confidence)
    consecutive_tool_failures = _count_consecutive(recent_turns, _is_tool_failure)

    # All three of these depend only on guest_message (never on each
    # other's result — retrieval in particular only needs dialogue_state/
    # flow_state to be *stored* on the eventual AssembledContext, not to
    # run the search itself) — run concurrently rather than back-to-back.
    # This is the single biggest fixed latency cost in the whole turn: two
    # LLM round trips and one embedding+DB round trip, previously fully
    # serialized.
    intent, entities, search_response = await asyncio.gather(
        classify_intent(guest_message, llm_provider=llm_provider),
        extract_entities(guest_message, llm_provider=llm_provider),
        retrieval_service.search(
            db,
            query_text=guest_message,
            embedding_provider=embedding_provider,
            reranker=reranker,
            guest_only=True,
            limit=8,  # matches app.orchestration.context.assembler._RETRIEVAL_LIMIT
            conversation_id=conversation_id,
            requested_channel="orchestration",
        ),
    )

    if customer is not None:
        # Not needed to produce this turn's reply — only affects a *future*
        # turn's GUEST_PROFILE block — so it must never sit on the guest's
        # critical path. Deferred to run after the response is sent when a
        # BackgroundTasks is available; falls back to inline (old behavior)
        # for callers that don't wire one up, e.g. tests.
        if background_tasks is not None:
            background_tasks.add_task(
                _record_inferences_background,
                customer_id=customer.id,
                entities=entities,
                conversation_id=conversation_id,
            )
        else:
            await memory.record_inferences(db, customer=customer, entities=entities, conversation_id=conversation_id)

    handoff = evaluate_handoff_requirement(
        intent=intent,
        consecutive_low_confidence_count=consecutive_low_confidence,
        consecutive_tool_failures=consecutive_tool_failures,
    )

    dialogue_state, flow_state = flow_engine.next_state(
        current_dialogue_state=conversation.current_state,
        current_flow_state=conversation.flow_state,
        intent=intent,
        mandatory_handoff=handoff.required,
    )

    # Backfilled from recent turns so a follow-up ("what's the final
    # price?") doesn't look like it's missing the check-in date / guest
    # count / room category the guest already gave a message or two ago —
    # entity extraction on its own only ever sees the current message.
    accumulated_entities = _merge_with_recent_entities(entities, recent_turns)
    missing_information = flow_engine.determine_missing_information(flow_state, accumulated_entities)
    date_validation_issues = validate_stay_dates(accumulated_entities.values)

    assembled = await assemble_context(
        db,
        conversation_id=conversation_id,
        customer=customer,
        guest_message=guest_message,
        dialogue_state=dialogue_state,
        flow_state=flow_state,
        embedding_provider=embedding_provider,
        reranker=reranker,
        search_response=search_response,
        stated_entities=accumulated_entities.values,
        date_validation_issues=date_validation_issues,
    )

    tool_decision = ToolDecision(tool_name=None)
    provider_usage: ProviderUsage | None = None
    response_text: str | None = None
    error_code: str | None = None
    error_message: str | None = None

    if handoff.required:
        response_text = _HANDOFF_ACKNOWLEDGMENT
    else:
        max_response_tokens = get_settings().orchestration_max_response_tokens
        try:
            prompt_messages = build_messages(context=assembled, intent=intent, channel=channel)
            llm_result = await llm_provider.complete(
                prompt_messages, tools=to_openai_tools(), max_tokens=max_response_tokens
            )
            provider_usage = ProviderUsage(
                provider=llm_result.provider,
                model=llm_result.model,
                latency_ms=llm_result.latency_ms,
                prompt_tokens=llm_result.prompt_tokens,
                completion_tokens=llm_result.completion_tokens,
            )
            response_text = llm_result.text

            if llm_result.tool_calls:
                call = llm_result.tool_calls[0]
                tool_decision = validate_tool_call(call)

                if tool_decision.decision == "execute":
                    try:
                        if call.tool_name == "search_resort_knowledge":
                            # Registered so the LLM can request a follow-up
                            # lookup, but per its own registry docstring
                            # it's executed here, not in tools.handlers
                            # (it needs the embedding provider/reranker the
                            # pipeline already holds).
                            output = await _search_resort_knowledge(
                                db,
                                query=call.arguments.get("query", guest_message),
                                conversation_id=conversation_id,
                                embedding_provider=embedding_provider,
                                reranker=reranker,
                            )
                        else:
                            output = await tool_handlers.execute_tool(
                                db,
                                tool_name=call.tool_name,
                                tool_input=call.arguments,
                                conversation_id=conversation_id,
                                customer_id=conversation.customer_id,
                                actor_user_id=actor_user_id,
                            )
                        tool_decision.output = output
                        tool_decision.status = "success"

                        if output.get("handoff_requested"):
                            handoff = evaluate_handoff_requirement(
                                intent=intent,
                                tool_signaled_handoff=True,
                                tool_handoff_reason=output.get("reason"),
                            )
                            dialogue_state, flow_state = flow_engine.apply_handoff(active=False)
                            response_text = _HANDOFF_ACKNOWLEDGMENT
                        else:
                            followup_messages = [
                                *prompt_messages,
                                # Must carry the exact tool_calls[] the
                                # provider proposed (not just text) so the
                                # following "tool" message's tool_call_id
                                # correlates to something real — the API
                                # rejects the reply otherwise.
                                LLMMessage(role="assistant", content=llm_result.text or "", tool_calls=[call]),
                                LLMMessage(role="tool", content=json.dumps(output), tool_call_id=call.call_id),
                            ]
                            followup_result = await llm_provider.complete(
                                followup_messages, max_tokens=max_response_tokens
                            )
                            response_text = followup_result.text
                            provider_usage = ProviderUsage(
                                provider=followup_result.provider,
                                model=followup_result.model,
                                latency_ms=provider_usage.latency_ms + followup_result.latency_ms,
                                prompt_tokens=(provider_usage.prompt_tokens or 0)
                                + (followup_result.prompt_tokens or 0),
                                completion_tokens=(provider_usage.completion_tokens or 0)
                                + (followup_result.completion_tokens or 0),
                            )
                    except Exception:  # noqa: BLE001 - a failed tool must never crash the guest's turn
                        tool_decision.status = "failed"
                        response_text = response_text or _TOOL_FAILURE_ACKNOWLEDGMENT
                # "needs_guest_confirmation" / "needs_staff_approval" / "denied":
                # the tool is not executed this turn; the model's own text
                # response (already in response_text) stands as-is.
        except AllProvidersFailedError as exc:
            error_code = exc.code
            error_message = str(exc)
            handoff = evaluate_handoff_requirement(intent=intent, provider_failed=True)
            dialogue_state, flow_state = flow_engine.apply_handoff(active=False)
            response_text = _PROVIDER_FAILURE_ACKNOWLEDGMENT

    if handoff.required and dialogue_state != "escalation":
        dialogue_state, flow_state = flow_engine.apply_handoff(active=False)

    validation_result = validate_response(
        response_text=response_text or "",
        tool_decision=tool_decision,
        retrieved_context=assembled.retrieved_context,
        missing_information=missing_information,
        channel=channel,
    )
    if validation_result.blocked:
        response_text = safe_fallback_response()
        if not handoff.required:
            handoff = HandoffDecision(
                required=True,
                priority="normal",
                department="front_desk",
                reason_code="retrieval_insufficient_for_sensitive_answer",
                summary="A generated response failed validation and was replaced with a safe fallback.",
            )
            dialogue_state, flow_state = flow_engine.apply_handoff(active=False)

    response_message = await messages_service.send_message(
        db,
        conversation_id=conversation_id,
        body=MessageCreateRequest(sender_type="ai", content_text=response_text),
        actor_user_id=actor_user_id,
    )

    await conversations_service.change_dialogue_state(
        db,
        conversation_id=conversation_id,
        new_state=dialogue_state,
        changed_by="ai",
        metadata={"flow_state": flow_state, "intent": intent.primary_intent},
        actor_user_id=actor_user_id,
    )
    conversation.flow_state = flow_state
    if handoff.required:
        await conversations_service.change_status(
            db, conversation_id=conversation_id, new_status="escalated", actor_user_id=actor_user_id
        )
    await db.commit()

    turn = OrchestrationTurn(
        conversation_id=conversation_id,
        message_id=message_id,
        response_message_id=response_message.id,
        detected_intent=intent.primary_intent,
        intent_confidence=intent.confidence,
        secondary_intents=[list(pair) for pair in intent.secondary_intents],
        extracted_entities=entities.values,
        missing_entities=missing_information.required_fields,
        flow_state=flow_state,
        retrieval_query=assembled.retrieved_context.query,
        citations=[
            {
                "chunk_id": str(c.chunk_id),
                "source_title": c.source_title,
                "source_priority": c.source_priority,
                "authoritative": c.authoritative,
                "score": c.score,
            }
            for c in assembled.retrieved_context.citations
        ],
        tool_name=tool_decision.tool_name,
        tool_input=tool_decision.tool_input,
        tool_output=tool_decision.output,
        tool_status=tool_decision.status,
        handoff_required=handoff.required,
        handoff_reason=handoff.reason_code,
        handoff_priority=handoff.priority,
        handoff_department=handoff.department,
        validation_result={
            "passed": validation_result.passed,
            "blocked": validation_result.blocked,
            "issues": [{"code": i.code, "severity": i.severity} for i in validation_result.issues],
        },
        provider_used=provider_usage.provider if provider_usage else None,
        model_used=provider_usage.model if provider_usage else None,
        latency_ms=provider_usage.latency_ms if provider_usage else None,
        token_usage=(
            {
                "prompt_tokens": provider_usage.prompt_tokens,
                "completion_tokens": provider_usage.completion_tokens,
            }
            if provider_usage
            else {}
        ),
        error_code=error_code,
        error_message=error_message,
    )
    await orch_service.save_orchestration_turn(db, turn)

    return OrchestrationResult(
        conversation_id=conversation_id,
        response_text=response_text,
        intent=intent,
        entities=entities,
        missing_information=missing_information,
        retrieved_context=assembled.retrieved_context,
        flow_state=flow_state,
        tool_decision=tool_decision,
        handoff_decision=handoff,
        validation_result=validation_result,
        provider_usage=provider_usage,
        error_code=error_code,
        error_message=error_message,
        created_at=turn.created_at,
    )
