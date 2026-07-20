import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import UUIDPrimaryKeyMixin
from app.database import Base
from app.feedback.constants import FEEDBACK_CATEGORIES, FEEDBACK_RATINGS, FEEDBACK_STATUSES


class CustomerFeedback(Base, UUIDPrimaryKeyMixin):
    """A structured, queryable feedback row — see constants.py for why this
    mirrors webchat's real thumbs-up/down vocabulary rather than a fabricated
    star scale. No TimestampMixin: only `status`/`assigned_agent_id` ever
    change after creation, same append-mostly shape as Notification."""

    __tablename__ = "customer_feedback"
    __table_args__ = (
        CheckConstraint(f"category IN {FEEDBACK_CATEGORIES}", name="ck_customer_feedback_category"),
        CheckConstraint(f"rating IN {FEEDBACK_RATINGS}", name="ck_customer_feedback_rating"),
        CheckConstraint(f"status IN {FEEDBACK_STATUSES}", name="ck_customer_feedback_status"),
    )

    category: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    rating: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    comment: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    turn_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orchestration_turns.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="new", index=True)
    assigned_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
