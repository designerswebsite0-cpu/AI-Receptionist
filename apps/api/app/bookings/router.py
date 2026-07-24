import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_audit_event
from app.bookings import repository, service
from app.bookings.schemas import RoomBookingOut, RoomBookingRejectRequest, RoomBookingStaffUpdateRequest, RoomTypeOut
from app.common.pagination import PageParams, build_page_meta
from app.common.responses import success
from app.customers import repository as customers_repository
from app.database import get_db
from app.deps import get_current_user
from app.users.models import User

router = APIRouter(prefix="/api/v1/bookings", tags=["bookings"])
room_types_router = APIRouter(prefix="/api/v1/room-types", tags=["bookings"])


async def _to_out(db: AsyncSession, booking) -> RoomBookingOut:
    names = await customers_repository.get_names_by_ids(db, [booking.customer_id])
    room_type = await repository.get_room_type(db, booking.room_type_id)
    return RoomBookingOut.from_model(
        booking,
        customer_name=names.get(booking.customer_id),
        room_type_name=room_type.name if room_type else None,
    )


@room_types_router.get("")
async def list_room_types(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    room_types = await service.list_room_types(db)
    return success({"items": [RoomTypeOut.from_model(rt).model_dump(mode="json") for rt in room_types]})


@router.get("")
async def list_bookings(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    params = PageParams(page=page, page_size=page_size)
    bookings, total = await repository.list_room_bookings(
        db, status=status, offset=params.offset, limit=params.page_size
    )

    customer_ids = [b.customer_id for b in bookings]
    names = await customers_repository.get_names_by_ids(db, customer_ids)
    room_types = {rt.id: rt for rt in await repository.list_room_types(db, active_only=False)}

    items = [
        RoomBookingOut.from_model(
            b, customer_name=names.get(b.customer_id), room_type_name=room_types.get(b.room_type_id).name
            if room_types.get(b.room_type_id) else None,
        ).model_dump(mode="json")
        for b in bookings
    ]
    return success({"items": items, "meta": build_page_meta(params, total).model_dump()})


@router.get("/{booking_id}")
async def get_booking(
    booking_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    booking = await service.get_booking_or_404(db, booking_id)
    out = await _to_out(db, booking)
    return success(out.model_dump(mode="json"))


@router.patch("/{booking_id}")
async def update_booking(
    booking_id: uuid.UUID,
    body: RoomBookingStaffUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    updates = body.model_dump(exclude_unset=True)
    booking = await service.update_booking_details(db, booking_id=booking_id, updates=updates)
    await record_audit_event(
        db,
        actor_user_id=user.id,
        action="room_booking.updated",
        resource_type="room_booking",
        resource_id=str(booking.id),
        before_state=None,
        after_state={k: str(v) for k, v in updates.items()},
        metadata={"fields": list(updates.keys())},
    )
    await db.commit()
    out = await _to_out(db, booking)
    return success(out.model_dump(mode="json"))


@router.post("/{booking_id}/confirm")
async def confirm_booking(
    booking_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    booking = await service.confirm_booking(db, booking_id=booking_id, actor_user_id=user.id)
    await record_audit_event(
        db,
        actor_user_id=user.id,
        action="room_booking.confirmed",
        resource_type="room_booking",
        resource_id=str(booking.id),
        before_state={"status": "pending_review"},
        after_state={"status": "confirmed", "sms_status": booking.confirmation_sms_status},
        metadata={},
    )
    await db.commit()
    out = await _to_out(db, booking)
    return success(out.model_dump(mode="json"))


@router.post("/{booking_id}/reject")
async def reject_booking(
    booking_id: uuid.UUID,
    body: RoomBookingRejectRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    booking = await service.reject_booking(
        db, booking_id=booking_id, staff_notes=body.staff_notes, actor_user_id=user.id
    )
    await record_audit_event(
        db,
        actor_user_id=user.id,
        action="room_booking.rejected",
        resource_type="room_booking",
        resource_id=str(booking.id),
        before_state={"status": "pending_review"},
        after_state={"status": "rejected"},
        metadata={},
    )
    await db.commit()
    out = await _to_out(db, booking)
    return success(out.model_dump(mode="json"))
