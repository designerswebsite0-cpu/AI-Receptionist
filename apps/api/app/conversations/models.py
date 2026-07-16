import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TimestampMixin, UUIDPrimaryKeyMixin
from app.conversations.constants import CHANNELS, DIALOGUE_STATES, PRIORITIES, STATE_CHANGED_BY, STATUSES
from app.database import Base


class Conversation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint(f"channel IN {CHANNELS}", name="ck_conversations_channel"),
        CheckConstraint(f"status IN {STATUSES}", name="ck_conversations_status"),
        CheckConstraint(f"priority IN {PRIORITIES}", name="ck_conversations_priority"),
        CheckConstraint(f"current_state IN {DIALOGUE_STATES}", name="ck_conversations_current_state"),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open", index=True)
    current_state: Mapped[str] = mapped_column(String(30), nullable=False, default="greeting")
    assigned_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="normal")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ai_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    human_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    summary: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    conversation_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class ConversationStateEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Audit trail of dialogue-state transitions — database.md principle
    that every table stay auditable. No transition-graph validation yet
    (any state to any state is allowed); that's a Phase 4 AI Orchestration
    concern, not a foundation-layer one."""

    __tablename__ = "conversation_state_events"
    __table_args__ = (CheckConstraint(f"changed_by IN {STATE_CHANGED_BY}", name="ck_conv_state_events_changed_by"),)

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_state: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_state: Mapped[str] = mapped_column(String(30), nullable=False)
    changed_by: Mapped[str] = mapped_column(String(20), nullable=False)
    event_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
