import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TimestampMixin, UUIDPrimaryKeyMixin
from app.database import Base


class WebchatSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Anonymous website-guest session identity — resolves an opaque
    browser cookie token to a (customer, conversation) pair server-side.
    Never stores the raw token, only its SHA-256 hash (app.webchat.service),
    so a leaked row can't be replayed as a live session."""

    __tablename__ = "webchat_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    session_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
