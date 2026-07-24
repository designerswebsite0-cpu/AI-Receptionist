"""Two webhook receivers plus a staff-facing REST surface.

Call-flow note (see docs/phase-9/ARCHITECTURE.md for the full picture):
Twilio's Elastic SIP Trunk carries the actual call audio straight to
LiveKit Cloud's SIP endpoint — this backend never proxies audio and never
generates TwiML for the live call. It only receives two kinds of
notifications: Twilio's voice status callback (call ringing/answered/
completed, with From/To/CallSid) and LiveKit's server webhook (room/
participant events, with the LiveKit room name) — together enough to keep
VoiceCall/Conversation rows in sync with a call neither of them fully
describes alone.
"""

import uuid

from fastapi import APIRouter, Depends, Form, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import PageParams, build_page_meta
from app.common.responses import success
from app.config import get_settings
from app.conversations import service as conversations_service
from app.customers import repository as customers_repository
from app.database import get_db
from app.deps import get_current_user
from app.errors import UnauthorizedError
from app.logging import get_logger
from app.users.models import User
from app.voice import livekit_client, repository, service
from app.voice.schemas import TakeoverResponse, VoiceCallOut
from app.voice.twilio_utils import validate_twilio_signature

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/voice", tags=["voice"])


@router.post("/twilio/status")
async def twilio_status_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
    CallSid: str = Form(...),
    From: str = Form(...),
    To: str = Form(...),
    CallStatus: str = Form(...),
) -> dict:
    settings = get_settings()
    body = await request.form()
    if settings.twilio_auth_token and not validate_twilio_signature(
        request, auth_token=settings.twilio_auth_token, params=dict(body)
    ):
        raise UnauthorizedError("Invalid Twilio signature")

    status_map = {
        "ringing": "ringing",
        "in-progress": "in_progress",
        "completed": "completed",
        "busy": "failed",
        "failed": "failed",
        "no-answer": "no_answer",
        "canceled": "failed",
    }
    mapped_status = status_map.get(CallStatus, "in_progress")

    if mapped_status == "ringing":
        await service.handle_incoming_call(db, from_number=From, to_number=To, twilio_call_sid=CallSid)
    else:
        await service.mark_call_status(db, twilio_call_sid=CallSid, status=mapped_status)

    return success({"received": True})


@router.post("/livekit/webhook")
async def livekit_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    body = (await request.body()).decode("utf-8")
    auth_header = request.headers.get("Authorization", "")
    event = livekit_client.verify_webhook(body=body, auth_header=auth_header)
    if event is None:
        raise UnauthorizedError("Invalid LiveKit webhook signature")

    # room.name is set by LiveKit's SIP dispatch rule to something call-
    # identifiable (commonly the SIP call ID); we only act on the events
    # that actually change what the dashboard needs to show.
    if event.event == "room_started" and event.room:
        # Best-effort match: nothing to key off here without the Twilio
        # CallSid also being embedded in the room name/metadata by the SIP
        # dispatch rule config — this handler exists so that association is
        # a one-line addition once a real dispatch rule format is chosen,
        # not a redesign. Logged, not raised, since a missed match must
        # never break the call.
        logger.info("livekit_room_started", extra={"room_name": event.room.name})
    elif event.event == "room_finished" and event.room:
        logger.info("livekit_room_finished", extra={"room_name": event.room.name})

    return success({"received": True})


@router.get("/calls")
async def list_calls(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    params = PageParams(page=page, page_size=page_size)
    calls, total = await repository.list_calls(db, status=status, offset=params.offset, limit=params.page_size)
    items = [await _to_out(db, call) for call in calls]
    meta = build_page_meta(params, total).model_dump()
    return success({"items": [i.model_dump(mode="json") for i in items], "meta": meta})


@router.get("/calls/active")
async def list_active_calls(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    calls = await repository.list_active_calls(db)
    items = [await _to_out(db, call) for call in calls]
    return success({"items": [i.model_dump(mode="json") for i in items]})


@router.get("/calls/{call_id}")
async def get_call(
    call_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    call = await service.get_call_or_404(db, call_id)
    out = await _to_out(db, call)
    return success(out.model_dump(mode="json"))


@router.post("/calls/{call_id}/takeover")
async def takeover_call(
    call_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    call, token = await service.takeover_call(
        db, call_id=call_id, actor_user_id=user.id, staff_name=user.full_name
    )
    settings = get_settings()
    return success(
        TakeoverResponse(
            livekit_url=settings.livekit_url,
            token=token,
            room_name=call.livekit_room_name,
            configured=livekit_client.is_configured() and call.livekit_room_name is not None,
        ).model_dump(mode="json")
    )


@router.post("/calls/{call_id}/end")
async def end_call(
    call_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    call = await service.end_call(db, call_id=call_id)
    out = await _to_out(db, call)
    return success(out.model_dump(mode="json"))


async def _to_out(db: AsyncSession, call) -> VoiceCallOut:
    conversation = await conversations_service.get_conversation_or_404(db, call.conversation_id)
    names = await customers_repository.get_names_by_ids(db, [conversation.customer_id])
    return VoiceCallOut.from_model(
        call,
        customer_name=names.get(conversation.customer_id),
        ai_active=conversation.ai_active,
        human_active=conversation.human_active,
    )
