import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.voice.constants import VOICE_CALL_STATUSES
from app.voice.models import VoiceCall

_ACTIVE_STATUSES = ("ringing", "in_progress")


async def create_call(db: AsyncSession, *, call: VoiceCall) -> VoiceCall:
    db.add(call)
    await db.flush()
    return call


async def get_call(db: AsyncSession, call_id: uuid.UUID) -> VoiceCall | None:
    return await db.get(VoiceCall, call_id)


async def get_call_by_twilio_sid(db: AsyncSession, twilio_call_sid: str) -> VoiceCall | None:
    result = await db.execute(select(VoiceCall).where(VoiceCall.twilio_call_sid == twilio_call_sid))
    return result.scalars().first()


async def get_call_by_conversation(db: AsyncSession, conversation_id: uuid.UUID) -> VoiceCall | None:
    result = await db.execute(
        select(VoiceCall).where(VoiceCall.conversation_id == conversation_id).order_by(VoiceCall.created_at.desc())
    )
    return result.scalars().first()


async def list_active_calls(db: AsyncSession) -> list[VoiceCall]:
    result = await db.execute(
        select(VoiceCall).where(VoiceCall.status.in_(_ACTIVE_STATUSES)).order_by(VoiceCall.created_at.desc())
    )
    return list(result.scalars().all())


async def list_calls(
    db: AsyncSession, *, status: str | None = None, offset: int = 0, limit: int = 50
) -> tuple[list[VoiceCall], int]:
    query = select(VoiceCall)
    count_query = select(func.count()).select_from(VoiceCall)
    if status:
        if status not in VOICE_CALL_STATUSES:
            status = None
        else:
            query = query.where(VoiceCall.status == status)
            count_query = count_query.where(VoiceCall.status == status)

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(query.order_by(VoiceCall.created_at.desc()).offset(offset).limit(limit))
    return list(result.scalars().all()), total


def compute_duration_seconds(started_at: datetime | None, ended_at: datetime) -> int | None:
    if started_at is None:
        return None
    return max(int((ended_at - started_at).total_seconds()), 0)
