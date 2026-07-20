import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import PageParams, build_page_meta
from app.common.responses import success
from app.database import get_db
from app.deps import get_current_user
from app.notifications import repository, service
from app.notifications.schemas import NotificationOut
from app.users.models import User

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(
    unread_only: bool = Query(default=False),
    notification_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    params = PageParams(page=page, page_size=page_size)
    notifications, total = await repository.list_notifications(
        db, unread_only=unread_only, notification_type=notification_type, offset=params.offset, limit=params.page_size
    )
    items = [NotificationOut.model_validate(n).model_dump(mode="json") for n in notifications]
    return success({"items": items, "meta": build_page_meta(params, total).model_dump()})


@router.get("/unread-count")
async def get_unread_count(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    count = await repository.count_unread(db)
    return success({"count": count})


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    notification = await service.mark_notification_read(db, notification_id=notification_id, actor_user_id=user.id)
    return success(NotificationOut.model_validate(notification).model_dump(mode="json"))


@router.post("/read-all")
async def mark_all_read(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    count = await service.mark_all_notifications_read(db, actor_user_id=user.id)
    return success({"marked_read": count})
