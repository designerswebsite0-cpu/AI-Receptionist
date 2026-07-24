import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.payments.constants import PAYMENT_METHODS
from app.payments.models import Payment


class PaymentOut(BaseModel):
    id: uuid.UUID
    room_booking_id: uuid.UUID | None
    customer_id: uuid.UUID
    customer_name: str | None = None
    amount: float
    currency: str
    method: str
    status: str
    provider: str
    provider_reference: str | None
    staff_notes: str | None
    recorded_by_user_id: uuid.UUID | None
    refunded_at: datetime | None
    created_at: datetime

    @classmethod
    def from_model(cls, payment: Payment, *, customer_name: str | None = None) -> "PaymentOut":
        return cls(
            id=payment.id,
            room_booking_id=payment.room_booking_id,
            customer_id=payment.customer_id,
            customer_name=customer_name,
            amount=float(payment.amount),
            currency=payment.currency,
            method=payment.method,
            status=payment.status,
            provider=payment.provider,
            provider_reference=payment.provider_reference,
            staff_notes=payment.staff_notes,
            recorded_by_user_id=payment.recorded_by_user_id,
            refunded_at=payment.refunded_at,
            created_at=payment.created_at,
        )


class RecordPaymentRequest(BaseModel):
    """Staff-initiated only — logs money already collected (or a
    placeholder online-pending row); never triggers a real charge."""

    room_booking_id: uuid.UUID | None = None
    customer_id: uuid.UUID
    amount: float = Field(gt=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    method: str
    staff_notes: str | None = Field(default=None, max_length=2000)

    @field_validator("method")
    @classmethod
    def _v_method(cls, value: str) -> str:
        if value not in PAYMENT_METHODS:
            raise ValueError(f"method must be one of {PAYMENT_METHODS}")
        return value


class RefundPaymentRequest(BaseModel):
    staff_notes: str | None = Field(default=None, max_length=2000)
