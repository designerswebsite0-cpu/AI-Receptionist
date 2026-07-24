import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_audit_event
from app.common.pagination import PageParams, build_page_meta
from app.common.responses import success
from app.customers import repository as customers_repository
from app.database import get_db
from app.deps import get_current_user
from app.payments import repository, service
from app.payments.schemas import PaymentOut, RecordPaymentRequest, RefundPaymentRequest
from app.users.models import User

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


async def _to_out(db: AsyncSession, payment) -> PaymentOut:
    names = await customers_repository.get_names_by_ids(db, [payment.customer_id])
    return PaymentOut.from_model(payment, customer_name=names.get(payment.customer_id))


@router.get("")
async def list_payments(
    room_booking_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    params = PageParams(page=page, page_size=page_size)
    payments, total = await repository.list_payments(
        db, room_booking_id=room_booking_id, status=status, offset=params.offset, limit=params.page_size
    )
    names = await customers_repository.get_names_by_ids(db, [p.customer_id for p in payments])
    items = [
        PaymentOut.from_model(p, customer_name=names.get(p.customer_id)).model_dump(mode="json") for p in payments
    ]
    return success({"items": items, "meta": build_page_meta(params, total).model_dump()})


@router.post("")
async def create_payment(
    body: RecordPaymentRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    payment = await service.record_payment(db, body=body, actor_user_id=user.id)
    await record_audit_event(
        db,
        actor_user_id=user.id,
        action="payment.recorded",
        resource_type="payment",
        resource_id=str(payment.id),
        after_state={"amount": str(payment.amount), "method": payment.method, "status": payment.status},
        metadata={},
    )
    await db.commit()
    out = await _to_out(db, payment)
    return success(out.model_dump(mode="json"))


@router.get("/{payment_id}")
async def get_payment(
    payment_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    payment = await service.get_payment_or_404(db, payment_id)
    out = await _to_out(db, payment)
    return success(out.model_dump(mode="json"))


@router.post("/{payment_id}/refund")
async def refund_payment(
    payment_id: uuid.UUID,
    body: RefundPaymentRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    payment = await service.refund_payment(db, payment_id=payment_id, staff_notes=body.staff_notes)
    await record_audit_event(
        db,
        actor_user_id=user.id,
        action="payment.refunded",
        resource_type="payment",
        resource_id=str(payment.id),
        before_state={"status": "paid"},
        after_state={"status": "refunded"},
        metadata={},
    )
    await db.commit()
    out = await _to_out(db, payment)
    return success(out.model_dump(mode="json"))
