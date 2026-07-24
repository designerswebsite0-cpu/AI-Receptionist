import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TimestampMixin, UUIDPrimaryKeyMixin
from app.database import Base
from app.payments.constants import PAYMENT_METHODS, PAYMENT_STATUSES


class Payment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A payment record — either money staff already physically collected
    (cash/card_on_arrival/bank_transfer, recorded as 'paid' the moment
    staff logs it) or a placeholder 'online_pending' row logged when a
    guest asks to pay before any gateway exists. No card data ever passes
    through this table or any code path that writes to it; provider is
    always 'manual' today (see constants.py's module docstring for the
    real-gateway seam)."""

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(f"method IN {PAYMENT_METHODS}", name="ck_payments_method"),
        CheckConstraint(f"status IN {PAYMENT_STATUSES}", name="ck_payments_status"),
    )

    room_booking_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("room_bookings.id", ondelete="SET NULL"), nullable=True, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )

    amount: Mapped[int] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    provider_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    staff_notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    recorded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
