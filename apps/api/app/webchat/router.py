"""Public, anonymous-guest webchat API — the only surface the resort
website's browser-facing code is allowed to reach for AI chat. Every
endpoint here resolves identity from an opaque session token
(app.webchat.deps.get_webchat_session), never from a client-supplied id,
and every message ultimately runs through the same
app.orchestration.pipeline.orchestrate() the staff dashboard uses.
"""

import uuid

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import PageParams, build_page_meta
from app.common.responses import success
from app.config import Settings, get_settings
from app.database import get_db
from app.errors import NotFoundError, ValidationErrorApp
from app.knowledge.embeddings import EmbeddingProvider
from app.knowledge.retrieval.reranker import Reranker
from app.messages.schemas import MessageOut
from app.orchestration.llm.base import LLMProvider
from app.orchestration.providers import get_llm_provider, get_orchestration_embedding_provider, get_reranker
from app.webchat import rate_limit, service
from app.webchat.constants import SESSION_COOKIE_NAME
from app.webchat.deps import get_webchat_session
from app.webchat.models import WebchatSession
from app.webchat.schemas import (
    WebchatContactIn,
    WebchatFeedbackIn,
    WebchatHandoffRequest,
    WebchatMessageIn,
)

router = APIRouter(prefix="/api/v1/webchat", tags=["webchat"])


def _require_enabled(settings: Settings = Depends(get_settings)) -> Settings:
    if not settings.webchat_enabled:
        raise NotFoundError("Website chat is not currently available")
    return settings


def _client_ip(request: Request) -> str:
    return rate_limit.client_ip(request.headers.get("x-forwarded-for"), request.client.host if request.client else None)


def _require_owns_session(session_id: uuid.UUID, session: WebchatSession) -> None:
    # The path's session_id is never itself an authorization check (the
    # token already resolved `session` server-side) — this only catches a
    # caller passing a mismatched id, and responds identically to "not
    # found" so it can't be used to probe which ids exist.
    if session.id != session_id:
        raise NotFoundError("Session not found")


@router.post("/sessions")
async def create_session(
    request: Request,
    response: Response,
    settings: Settings = Depends(_require_enabled),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await rate_limit.enforce(
        f"webchat:ratelimit:sessions:{_client_ip(request)}",
        limit=settings.webchat_conversation_limit_per_ip_per_hour,
        window_seconds=3600,
    )
    result = await service.start_session(db, settings=settings)

    # Cookie is set for a same-origin deployment talking to this API
    # directly; the intended production shape (docs/phase-5/WEBCHAT_ARCHITECTURE.md)
    # is the website's own server reading `token` from this response body
    # once and forwarding it server-to-server on later calls via the
    # X-Webchat-Session-Token header — this cookie is a convenience, not
    # the only supported path.
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=result.token or "",
        max_age=settings.webchat_session_ttl_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )
    return success(result.model_dump(mode="json"))


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: uuid.UUID,
    session: WebchatSession = Depends(get_webchat_session),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _require_owns_session(session_id, session)
    result = await service.get_session_state(db, session=session)
    return success(result.model_dump(mode="json"))


@router.delete("/sessions/{session_id}")
async def end_session(
    session_id: uuid.UUID,
    response: Response,
    session: WebchatSession = Depends(get_webchat_session),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _require_owns_session(session_id, session)
    await service.end_session(db, session=session)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return success({"ended": True})


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: uuid.UUID,
    body: WebchatMessageIn,
    request: Request,
    settings: Settings = Depends(_require_enabled),
    session: WebchatSession = Depends(get_webchat_session),
    db: AsyncSession = Depends(get_db),
    llm_provider: LLMProvider = Depends(get_llm_provider),
    embedding_provider: EmbeddingProvider = Depends(get_orchestration_embedding_provider),
    reranker: Reranker = Depends(get_reranker),
) -> dict:
    _require_owns_session(session_id, session)
    if len(body.message) > settings.webchat_max_message_length:
        raise ValidationErrorApp(
            f"Message is too long (max {settings.webchat_max_message_length} characters)"
        )

    ip = _client_ip(request)
    await rate_limit.enforce(
        f"webchat:ratelimit:messages:session:{session.id}",
        limit=settings.webchat_rate_limit_per_minute,
        window_seconds=60,
    )
    await rate_limit.enforce(
        f"webchat:ratelimit:messages:ip:{ip}",
        limit=settings.webchat_message_limit_per_ip_per_minute,
        window_seconds=60,
    )

    result = await service.send_message(
        db,
        session=session,
        text=body.message,
        client_message_id=body.client_message_id,
        llm_provider=llm_provider,
        embedding_provider=embedding_provider,
        reranker=reranker,
    )
    return success(result.model_dump(mode="json"))


@router.get("/sessions/{session_id}/messages")
async def list_messages(
    session_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    session: WebchatSession = Depends(get_webchat_session),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _require_owns_session(session_id, session)
    params = PageParams(page=page, page_size=page_size)
    messages, total = await service.list_transcript(db, session=session, offset=params.offset, limit=params.page_size)
    return success(
        {
            "items": [MessageOut.model_validate(m).model_dump(mode="json") for m in messages],
            "meta": build_page_meta(params, total).model_dump(),
        }
    )


@router.post("/sessions/{session_id}/handoff")
async def request_handoff(
    session_id: uuid.UUID,
    body: WebchatHandoffRequest,
    session: WebchatSession = Depends(get_webchat_session),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _require_owns_session(session_id, session)
    result = await service.request_handoff(db, session=session, reason=body.reason)
    return success(result.model_dump(mode="json"))


@router.post("/sessions/{session_id}/feedback")
async def submit_feedback(
    session_id: uuid.UUID,
    body: WebchatFeedbackIn,
    session: WebchatSession = Depends(get_webchat_session),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _require_owns_session(session_id, session)
    await service.submit_feedback(db, session=session, turn_id=body.turn_id, rating=body.rating, comment=body.comment)
    return success({"recorded": True})


@router.post("/sessions/{session_id}/contact")
async def capture_contact(
    session_id: uuid.UUID,
    body: WebchatContactIn,
    session: WebchatSession = Depends(get_webchat_session),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _require_owns_session(session_id, session)
    await service.capture_contact(
        db,
        session=session,
        phone=body.phone,
        email=body.email,
        full_name=body.full_name,
        marketing_consent=body.marketing_consent,
    )
    # Deliberately generic — never reveals whether the phone/email already
    # belonged to an existing customer (brief §8).
    return success({"message": "Thank you — we've noted your contact details."})
