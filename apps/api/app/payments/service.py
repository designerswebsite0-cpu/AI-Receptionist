"""Phase 7's second operation — deliberately a placeholder (per the
2026-07-24 brief: "use placeholder, since I dont have a env right now,
we'll check about payments fully at the end"). Every function here either
records money staff already physically collected, or logs a guest's intent
to pay online before any real gateway exists. THE REAL INTEGRATION SEAM:
when a gateway (Stripe/Razorpay/etc.) is chosen, add its credentials to
app.config.Settings, then change _resolve_status below to call out to that
provider instead of hard-coding "online_pending" -> "pending" — nothing
else in this module, the schema, or the dashboard needs to change.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import NotFoundError, ValidationErrorApp
from app.notifications.service import notify
from app.payments import repository
from app.payments.constants import IMMEDIATELY_PAID_METHODS
from app.payments.models import Payment
from app.payments.schemas import RecordPaymentRequest


def _resolve_status(method: str) -> str:
    return "paid" if method in IMMEDIATELY_PAID_METHODS else "pending"


async def record_payment(
    db: AsyncSession, *, body: RecordPaymentRequest, actor_user_id: uuid.UUID
) -> Payment:
    payment = Payment(
        room_booking_id=body.room_booking_id,
        customer_id=body.customer_id,
        amount=body.amount,
        currency=body.currency.upper(),
        method=body.method,
        status=_resolve_status(body.method),
        provider="manual",
        staff_notes=body.staff_notes,
        recorded_by_user_id=actor_user_id,
    )
    payment = await repository.create_payment(db, payment=payment)
    await db.commit()
    await db.refresh(payment)
    return payment


async def record_payment_enquiry(
    db: AsyncSession,
    *,
    conversation_id: uuid.UUID,
    customer_id: uuid.UUID,
    room_booking_id: uuid.UUID | None,
    amount: float | None,
    notes: str | None,
) -> Payment:
    """AI-facing — never marks anything 'paid'. Always 'online_pending',
    always staff follow-up required, exactly like create_room_booking's
    'pending_review' guarantee."""
    payment = Payment(
        conversation_id=conversation_id,
        customer_id=customer_id,
        room_booking_id=room_booking_id,
        amount=amount or 0,
        currency="INR",
        method="online_pending",
        status="pending",
        provider="manual",
        staff_notes=notes,
    )
    payment = await repository.create_payment(db, payment=payment)
    await db.commit()
    await db.refresh(payment)

    await notify(
        db,
        notification_type="payment_enquiry_received",
        title="Guest wants to pay — no online gateway yet",
        body=f"Amount: {amount}" if amount else "Amount not stated",
        resource_type="payment",
        resource_id=str(payment.id),
    )
    return payment


async def get_payment_or_404(db: AsyncSession, payment_id: uuid.UUID) -> Payment:
    payment = await repository.get_payment(db, payment_id)
    if payment is None:
        raise NotFoundError("Payment not found")
    return payment


async def refund_payment(db: AsyncSession, *, payment_id: uuid.UUID, staff_notes: str | None) -> Payment:
    payment = await get_payment_or_404(db, payment_id)
    if payment.status != "paid":
        raise ValidationErrorApp(f"Payment is '{payment.status}', not 'paid' — nothing to refund")

    payment.status = "refunded"
    payment.refunded_at = datetime.now(UTC)
    if staff_notes:
        payment.staff_notes = staff_notes

    await db.commit()
    await db.refresh(payment)
    return payment
