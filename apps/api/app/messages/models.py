import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.database import Base
from app.messages.constants import ATTACHMENT_TYPES, CONTENT_TYPES, DELIVERY_STATUSES, DIRECTIONS, SENDER_TYPES


class Message(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """Channel-independent message — the same shape for WhatsApp, web chat,
    and (later) voice-call transcripts. Channel adapters normalize into
    this shape rather than the platform branching on channel per message.
    """

    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(f"direction IN {DIRECTIONS}", name="ck_messages_direction"),
        CheckConstraint(f"sender_type IN {SENDER_TYPES}", name="ck_messages_sender_type"),
        CheckConstraint(f"content_type IN {CONTENT_TYPES}", name="ck_messages_content_type"),
        CheckConstraint(f"delivery_status IN {DELIVERY_STATUSES}", name="ck_messages_delivery_status"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    sender_type: Mapped[str] = mapped_column(String(20), nullable=False)
    sender_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    content_type: Mapped[str] = mapped_column(String(20), nullable=False, default="text")
    content_text: Mapped[str | None] = mapped_column(String(8000), nullable=True)
    delivery_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Populated once a real channel adapter (Phase 6 WhatsApp) exists;
    # required up front by the idempotency rules in rules.md/architecture.md
    # so retried webhook deliveries can be deduplicated without a later
    # migration to add it.
    external_message_id: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    message_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    attachments: Mapped[list["MessageAttachment"]] = relationship(
        "MessageAttachment", cascade="all, delete-orphan", lazy="selectin"
    )


class MessageAttachment(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """Points at a private Supabase Storage object — never a public URL.
    Only backend code generates short-lived signed URLs from storage_path
    (architecture.md §6/§12)."""

    __tablename__ = "message_attachments"
    __table_args__ = (CheckConstraint(f"attachment_type IN {ATTACHMENT_TYPES}", name="ck_attachments_type"),)

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attachment_type: Mapped[str] = mapped_column(String(20), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
