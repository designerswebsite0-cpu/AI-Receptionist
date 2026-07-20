import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import PageParams, build_page_meta
from app.common.responses import success
from app.customers import repository as customers_repository
from app.database import get_db
from app.deps import get_current_user
from app.service_requests import repository, service
from app.service_requests.schemas import BookingRequestOut, BookingRequestUpdateRequest
from app.users.models import User

router = APIRouter(prefix="/api/v1/bookings", tags=["bookings"])


@router.get("")
async def list_bookings(
    status: str | None = Query(default=None),
    booking_status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    params = PageParams(page=page, page_size=page_size)
    requests, total = await repository.list_booking_requests(
        db, status=status, booking_status=booking_status, offset=params.offset, limit=params.page_size
    )
    names = await customers_repository.get_names_by_ids(db, [r.customer_id for r in requests])
    items = [
        BookingRequestOut.from_service_request(r, customer_name=names.get(r.customer_id)).model_dump(mode="json")
        for r in requests
    ]
    return success({"items": items, "meta": build_page_meta(params, total).model_dump()})


@router.get("/{request_id}")
async def get_booking(
    request_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    request = await service.get_booking_request_or_404(db, request_id)
    names = await customers_repository.get_names_by_ids(db, [request.customer_id])
    out = BookingRequestOut.from_service_request(request, customer_name=names.get(request.customer_id))
    return success(out.model_dump(mode="json"))


@router.patch("/{request_id}")
async def update_booking(
    request_id: uuid.UUID,
    body: BookingRequestUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    request = await service.update_booking_request(db, request_id=request_id, body=body, actor_user_id=user.id)
    names = await customers_repository.get_names_by_ids(db, [request.customer_id])
    out = BookingRequestOut.from_service_request(request, customer_name=names.get(request.customer_id))
    return success(out.model_dump(mode="json"))
