import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import UUIDPrimaryKeyMixin
from app.database import Base
from app.notifications.constants import NOTIFICATION_TYPES


class Notification(Base, UUIDPrimaryKeyMixin):
    """A resort-wide, shared notification feed entry — see constants.py for
    why this has no per-recipient scoping. Append-only except for the
    read_at/read_by_user_id pair, so no TimestampMixin (no updated_at
    needed beyond that one mutable fact, same shape as AuditLog)."""

    __tablename__ = "notifications"
    __table_args__ = (CheckConstraint(f"notification_type IN {NOTIFICATION_TYPES}", name="ck_notifications_type"),)

    notification_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
