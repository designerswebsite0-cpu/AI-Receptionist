import uuid
from datetime import datetime

from pydantic import BaseModel

from app.voice.models import VoiceCall


class VoiceCallOut(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    customer_name: str | None = None
    twilio_call_sid: str | None
    from_number: str | None
    to_number: str | None
    direction: str
    status: str
    outcome: str | None
    started_at: datetime | None
    ended_at: datetime | None
    duration_seconds: int | None
    ai_active: bool | None = None
    human_active: bool | None = None
    created_at: datetime

    @classmethod
    def from_model(
        cls,
        call: VoiceCall,
        *,
        customer_name: str | None = None,
        ai_active: bool | None = None,
        human_active: bool | None = None,
    ) -> "VoiceCallOut":
        return cls(
            id=call.id,
            conversation_id=call.conversation_id,
            customer_name=customer_name,
            twilio_call_sid=call.twilio_call_sid,
            from_number=call.from_number,
            to_number=call.to_number,
            direction=call.direction,
            status=call.status,
            outcome=call.outcome,
            started_at=call.started_at,
            ended_at=call.ended_at,
            duration_seconds=call.duration_seconds,
            ai_active=ai_active,
            human_active=human_active,
            created_at=call.created_at,
        )


class TakeoverResponse(BaseModel):
    """Mints a LiveKit access token for a staff member's browser to join
    the live call room directly — actual real-time audio join happens
    client-side via livekit-client (JS SDK), not through this backend."""

    livekit_url: str | None
    token: str | None
    room_name: str | None
    configured: bool
