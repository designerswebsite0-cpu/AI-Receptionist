"""LiveKit Agents worker — Phase 9 inbound voice. Runs as its OWN process
(`python -m app.voice.agent dev` / `start`), separate from the FastAPI app,
dispatched by LiveKit whenever a call arrives via the configured SIP
inbound trunk + dispatch rule (see docs/phase-9/ARCHITECTURE.md for the
full Twilio Elastic SIP Trunk -> LiveKit call path — this process never
talks to Twilio directly).

The one deliberate design choice worth calling out: ResortVoiceAgent
overrides llm_node() to call app.orchestration.pipeline.orchestrate() — the
exact same function every other channel (webchat, WhatsApp) already calls
— instead of wiring a LiveKit LLM plugin. This is what "voice must become
another channel that enters the existing orchestration pipeline" (the
2026-07-24 brief) means in code: RAG, prompt building, intent detection,
tool execution, and handoff decisions are not reimplemented here, they are
literally the same function call blocked chat and voice both make. Handoff
in particular therefore requires zero new logic on the AI side — once
orchestrate() (via the same conversations_service.change_status escalation
path text channels already use) flips ai_active False, this llm_node
returns silence on every subsequent turn exactly like the text pipeline's
own ai_locked_out branch.
"""

import uuid

from livekit.agents import Agent, AgentSession, JobContext, ModelSettings, WorkerOptions, cli
from livekit.agents.llm import ChatContext, FunctionTool
from livekit.plugins import deepgram, elevenlabs

from app.config import get_settings
from app.conversations import service as conversations_service
from app.database import AsyncSessionLocal
from app.knowledge.embeddings import get_embedding_provider
from app.knowledge.retrieval.reranker import HeuristicReranker
from app.logging import configure_logging, get_logger
from app.messages import service as messages_service
from app.messages.schemas import MessageCreateRequest
from app.orchestration.pipeline import orchestrate
from app.voice import service as voice_service
from app.voice.providers import get_voice_llm_provider

logger = get_logger("app.voice.agent")

_INSTRUCTIONS = (
    "You are Aranya, RKPR Resort's front-desk receptionist, speaking on a phone call. "
    "Speak the way a real front-desk person answers the phone: short, natural sentences, "
    "no lists, no markdown, no long explanations — this is heard, not read."
)

_FALLBACK_LINE = "Sorry, could you say that again?"
_SILENT_ESCALATION_ACK = "One moment, let me get a team member for you."


class ResortVoiceAgent(Agent):
    """One instance per call. conversation_id/customer_id are resolved once
    in entrypoint() below (from the Twilio status-callback row created
    before the SIP leg even connects, or created fresh as a fallback) and
    passed in here — never re-derived per turn."""

    def __init__(self, *, conversation_id: uuid.UUID, customer_id: uuid.UUID):
        super().__init__(instructions=_INSTRUCTIONS, llm=None, turn_detection="stt")
        self._conversation_id = conversation_id
        self._customer_id = customer_id
        self._llm_provider = get_voice_llm_provider()
        self._embedding_provider = get_embedding_provider()
        self._reranker = HeuristicReranker()
        self._announced_escalation = False

    async def llm_node(
        self, chat_ctx: ChatContext, tools: list[FunctionTool], model_settings: ModelSettings
    ) -> str:
        guest_message = ""
        for item in reversed(chat_ctx.items):
            if getattr(item, "role", None) == "user":
                guest_message = (item.text_content or "").strip()
                break

        if not guest_message:
            return _FALLBACK_LINE

        async with AsyncSessionLocal() as db:
            conversation = await conversations_service.get_conversation_or_404(db, self._conversation_id)
            if not conversation.ai_active:
                if not self._announced_escalation:
                    self._announced_escalation = True
                    return _SILENT_ESCALATION_ACK
                return ""

            message = await messages_service.send_message(
                db,
                conversation_id=self._conversation_id,
                body=MessageCreateRequest(sender_type="customer", content_text=guest_message),
                actor_user_id=None,
            )
            try:
                result = await orchestrate(
                    db,
                    conversation_id=self._conversation_id,
                    message_id=message.id,
                    guest_message=guest_message,
                    channel="voice",
                    llm_provider=self._llm_provider,
                    embedding_provider=self._embedding_provider,
                    reranker=self._reranker,
                    actor_user_id=None,
                )
            except Exception:  # noqa: BLE001 - never expose a technical error to the caller
                logger.exception("voice_orchestrate_failed", extra={"conversation_id": str(self._conversation_id)})
                return _FALLBACK_LINE

            return result.response_text or _FALLBACK_LINE


def _extract_sip_metadata(participant) -> tuple[str | None, str | None, str | None]:
    """Reads Twilio call identity off the SIP participant's attributes.
    Exact attribute keys depend on the dispatch rule format chosen when the
    real LiveKit SIP inbound trunk is configured — never raises if the
    expected keys aren't present (e.g. during local testing without a real
    SIP call), it just falls back to unknowns."""
    attributes = getattr(participant, "attributes", None) or {}
    from_number = attributes.get("sip.phoneNumber")
    to_number = attributes.get("sip.trunkPhoneNumber")
    call_sid = attributes.get("sip.twilio.callSid") or attributes.get("sip.callID")
    return from_number, to_number, call_sid


async def entrypoint(ctx: JobContext) -> None:
    settings = get_settings()
    await ctx.connect()

    participant = await ctx.wait_for_participant()
    from_number, to_number, call_sid = _extract_sip_metadata(participant)

    async with AsyncSessionLocal() as db:
        conversation, call = await voice_service.handle_incoming_call(
            db,
            from_number=from_number or f"unknown:{participant.identity}",
            to_number=to_number or settings.twilio_phone_number or "unknown",
            twilio_call_sid=call_sid or f"livekit:{ctx.room.name}",
        )
        await voice_service.mark_call_status(
            db, twilio_call_sid=call.twilio_call_sid, status="in_progress", livekit_room_name=ctx.room.name
        )
        conversation_id = conversation.id
        customer_id = conversation.customer_id

    session = AgentSession(
        stt=deepgram.STTv2(api_key=settings.deepgram_api_key or None),
        tts=elevenlabs.TTS(
            voice_id=settings.elevenlabs_voice_id or "bIHbv24MWmeRgasZH58o",
            model="eleven_flash_v2_5",
            api_key=settings.elevenlabs_api_key or None,
        ),
        llm=None,
        allow_interruptions=True,
    )
    agent = ResortVoiceAgent(conversation_id=conversation_id, customer_id=customer_id)

    async def _on_call_ended() -> None:
        async with AsyncSessionLocal() as db:
            await voice_service.mark_call_status(db, twilio_call_sid=call.twilio_call_sid, status="completed")

    ctx.add_shutdown_callback(_on_call_ended)

    await session.start(agent, room=ctx.room)


def _prewarm(proc) -> None:
    # No local model to warm (STT/TTS are both remote APIs, no Silero VAD
    # in this build — see pyproject.toml's comment on the onnxruntime cp314
    # wheel gap) — kept as an explicit no-op rather than omitted, since
    # WorkerOptions.prewarm_fnc is part of the standard worker lifecycle
    # future plugins (e.g. a local VAD) would hook into.
    return None


if __name__ == "__main__":
    configure_logging("INFO")
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=_prewarm, agent_name="rkpr-voice-receptionist"))
