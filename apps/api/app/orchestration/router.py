"""API layer for the AI orchestration pipeline — all endpoints require
`get_current_user` (this deployment's single-resort auth model, per
docs/CLAUDE.md's "Single-Resort Access Model": no role/permission checks
beyond authentication). Every endpoint here is a thin wrapper over already-
tested service/pipeline functions; no new business logic lives in this file.
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import PageParams, build_page_meta
from app.common.responses import success
from app.config import get_settings
from app.conversations import service as conversations_service
from app.database import get_db
from app.deps import get_current_user
from app.errors import NotFoundError
from app.knowledge.embeddings import EmbeddingProvider
from app.knowledge.retrieval.reranker import Reranker
from app.messages import repository as messages_repository
from app.orchestration import repository as orch_repository
from app.orchestration.flow import engine as flow_engine
from app.orchestration.llm.base import LLMProvider
from app.orchestration.pipeline import orchestrate
from app.orchestration.providers import get_llm_provider, get_orchestration_embedding_provider, get_reranker
from app.orchestration.schemas import (
    ConversationStateOut,
    ForceHandoffRequest,
    HandoffDecisionOut,
    OrchestrationTurnOut,
    ProcessMessageRequest,
    ProcessMessageResponse,
    ProviderHealthOut,
    ProviderUsageOut,
    TurnCitationOut,
)
from app.users.models import User

router = APIRouter(prefix="/api/v1/orchestration", tags=["orchestration"])


@router.post("/messages/{conversation_id}/process")
async def process_message(
    conversation_id: uuid.UUID,
    body: ProcessMessageRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm_provider: LLMProvider = Depends(get_llm_provider),
    embedding_provider: EmbeddingProvider = Depends(get_orchestration_embedding_provider),
    reranker: Reranker = Depends(get_reranker),
) -> dict:
    """Runs the full pipeline for one already-persisted guest message
    (`body.message_id`) — the single entry point every channel (webchat
    now, WhatsApp/voice later) calls. Idempotent: replaying an already-
    processed message_id returns the prior outcome without re-invoking the
    LLM or re-executing any tool (app.orchestration.pipeline.orchestrate's
    own guarantee, not reimplemented here).
    """
    message = await messages_repository.get_message(db, body.message_id)
    if message is None or message.conversation_id != conversation_id:
        raise NotFoundError("Message not found in this conversation")

    result = await orchestrate(
        db,
        conversation_id=conversation_id,
        message_id=body.message_id,
        guest_message=message.content_text or "",
        channel=body.channel,
        llm_provider=llm_provider,
        embedding_provider=embedding_provider,
        reranker=reranker,
        actor_user_id=user.id,
        background_tasks=background_tasks,
    )

    return success(
        ProcessMessageResponse(
            conversation_id=result.conversation_id,
            response_text=result.response_text,
            intent=result.intent.primary_intent,
            intent_confidence=result.intent.confidence,
            missing_information=result.missing_information.required_fields,
            flow_state=result.flow_state,
            handoff=HandoffDecisionOut(
                required=result.handoff_decision.required,
                priority=result.handoff_decision.priority,
                department=result.handoff_decision.department,
                reason_code=result.handoff_decision.reason_code,
                summary=result.handoff_decision.summary,
            ),
            validation_passed=result.validation_result.passed,
            provider_usage=(
                ProviderUsageOut(
                    provider=result.provider_usage.provider,
                    model=result.provider_usage.model,
                    latency_ms=result.provider_usage.latency_ms,
                    prompt_tokens=result.provider_usage.prompt_tokens,
                    completion_tokens=result.provider_usage.completion_tokens,
                )
                if result.provider_usage
                else None
            ),
            error_code=result.error_code,
        ).model_dump(mode="json")
    )


@router.get("/conversations/{conversation_id}/state")
async def get_conversation_state(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    conversation = await conversations_service.get_conversation_or_404(db, conversation_id)
    recent_turns = await orch_repository.list_turns_for_conversation(db, conversation_id, limit=1)
    latest = recent_turns[0] if recent_turns else None

    return success(
        ConversationStateOut(
            conversation_id=conversation.id,
            current_state=conversation.current_state,
            flow_state=conversation.flow_state,
            status=conversation.status,
            ai_active=conversation.ai_active,
            human_active=conversation.human_active,
            last_intent=latest.detected_intent if latest else None,
            last_intent_confidence=latest.intent_confidence if latest else None,
        ).model_dump(mode="json")
    )


@router.get("/conversations/{conversation_id}/turns")
async def list_conversation_turns(
    conversation_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await conversations_service.get_conversation_or_404(db, conversation_id)
    params = PageParams(page=page, page_size=page_size)
    # list_turns_for_conversation takes a flat limit, not offset/limit —
    # fetch enough to slice the requested page from, capped generously.
    all_turns = await orch_repository.list_turns_for_conversation(
        db, conversation_id, limit=params.offset + params.page_size
    )
    page_turns = all_turns[params.offset : params.offset + params.page_size]

    return success(
        {
            "items": [OrchestrationTurnOut.model_validate(t).model_dump(mode="json") for t in page_turns],
            "meta": build_page_meta(params, len(all_turns)).model_dump(),
        }
    )


@router.get("/turns/{turn_id}/citations")
async def get_turn_citations(
    turn_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    turn = await orch_repository.get_turn(db, turn_id)
    if turn is None:
        raise NotFoundError("Orchestration turn not found")
    citations = [TurnCitationOut.model_validate(c).model_dump(mode="json") for c in turn.citations]
    return success({"items": citations})


@router.get("/turns/{turn_id}/tool-executions")
async def get_turn_tool_executions(
    turn_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    turn = await orch_repository.get_turn(db, turn_id)
    if turn is None:
        raise NotFoundError("Orchestration turn not found")
    if turn.tool_name is None:
        return success({"items": []})
    return success(
        {
            "items": [
                {
                    "tool_name": turn.tool_name,
                    "tool_input": turn.tool_input,
                    "tool_output": turn.tool_output,
                    "tool_status": turn.tool_status,
                }
            ]
        }
    )


@router.post("/conversations/{conversation_id}/handoff")
async def force_handoff(
    conversation_id: uuid.UUID,
    body: ForceHandoffRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Staff-initiated handoff — independent of the deterministic handoff
    policy engine's own automatic triggers (app.orchestration.handoff.engine);
    a staff member can always pull a conversation into escalation manually."""
    conversation = await conversations_service.get_conversation_or_404(db, conversation_id)
    new_state, new_flow_state = flow_engine.apply_handoff(active=False)

    await conversations_service.change_dialogue_state(
        db,
        conversation_id=conversation_id,
        new_state=new_state,
        changed_by="human",
        metadata={"flow_state": new_flow_state, "reason": body.reason, "forced_by": str(user.id)},
        actor_user_id=user.id,
    )
    conversation.flow_state = new_flow_state
    await conversations_service.change_status(
        db, conversation_id=conversation_id, new_status="escalated", actor_user_id=user.id
    )

    return success(
        ConversationStateOut(
            conversation_id=conversation.id,
            current_state=new_state,
            flow_state=new_flow_state,
            status="escalated",
            ai_active=conversation.ai_active,
            human_active=conversation.human_active,
            last_intent=None,
            last_intent_confidence=None,
        ).model_dump(mode="json")
    )


@router.post("/conversations/{conversation_id}/release")
async def release_to_ai(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Staff releases a conversation back to the AI after handling a
    handoff — resumes at discovering_needs if it was escalated (never loops
    straight back into another handoff), per
    app.orchestration.flow.engine.resume_after_handoff's own design."""
    conversation = await conversations_service.get_conversation_or_404(db, conversation_id)
    new_state, new_flow_state = flow_engine.resume_after_handoff(conversation.current_state, conversation.flow_state)

    await conversations_service.change_dialogue_state(
        db,
        conversation_id=conversation_id,
        new_state=new_state,
        changed_by="human",
        metadata={"flow_state": new_flow_state, "released_by": str(user.id)},
        actor_user_id=user.id,
    )
    conversation.flow_state = new_flow_state
    await conversations_service.change_status(
        db, conversation_id=conversation_id, new_status="ai_handling", actor_user_id=user.id
    )

    return success(
        ConversationStateOut(
            conversation_id=conversation.id,
            current_state=new_state,
            flow_state=new_flow_state,
            status="ai_handling",
            ai_active=True,
            human_active=False,
            last_intent=None,
            last_intent_confidence=None,
        ).model_dump(mode="json")
    )


@router.get("/health/providers")
async def provider_health(user: User = Depends(get_current_user)) -> dict:
    """Configuration presence only — never a real API call (would cost
    money on every health check) and never the key values themselves."""
    settings = get_settings()
    return success(
        ProviderHealthOut(
            llm_configured=bool(settings.openai_api_key),
            llm_fallback_configured=bool(settings.groq_api_key),
            embedding_configured=bool(settings.openai_api_key),
        ).model_dump(mode="json")
    )
