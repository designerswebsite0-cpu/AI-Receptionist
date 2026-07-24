import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TimestampMixin, UUIDPrimaryKeyMixin
from app.database import Base
from app.voice.constants import VOICE_CALL_DIRECTIONS, VOICE_CALL_OUTCOMES, VOICE_CALL_STATUSES


class VoiceCall(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Call-specific metadata for one inbound phone call — the transcript
    itself lives in the existing messages table (conversation_id below,
    channel='voice'), never duplicated here. See constants.py's module
    docstring."""

    __tablename__ = "voice_calls"
    __table_args__ = (
        CheckConstraint(f"status IN {VOICE_CALL_STATUSES}", name="ck_voice_calls_status"),
        CheckConstraint(f"direction IN {VOICE_CALL_DIRECTIONS}", name="ck_voice_calls_direction"),
        CheckConstraint(f"outcome IS NULL OR outcome IN {VOICE_CALL_OUTCOMES}", name="ck_voice_calls_outcome"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    twilio_call_sid: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)
    livekit_room_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    from_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False, default="inbound")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ringing", index=True)
    outcome: Mapped[str | None] = mapped_column(String(20), nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
