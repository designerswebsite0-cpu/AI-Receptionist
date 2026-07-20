import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import PageParams, build_page_meta
from app.common.responses import success
from app.conversations import repository as conversations_repository
from app.database import get_db
from app.deps import get_current_user
from app.users import repository, service
from app.users.models import User
from app.users.schemas import UserOut, UserUpdateRequest

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("")
async def list_users(
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    params = PageParams(page=page, page_size=page_size)
    users, total = await repository.list_users(
        db, status=status, search=search, offset=params.offset, limit=params.page_size
    )
    counts = await conversations_repository.count_open_conversations_by_agent(db, [u.id for u in users])
    items = [
        UserOut.model_validate(u)
        .model_copy(update={"assigned_conversation_count": counts.get(u.id, 0)})
        .model_dump(mode="json")
        for u in users
    ]
    return success({"items": items, "meta": build_page_meta(params, total).model_dump()})


@router.get("/{user_id}")
async def get_user(
    user_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    staff_user = await service.get_user_or_404(db, user_id)
    counts = await conversations_repository.count_open_conversations_by_agent(db, [staff_user.id])
    out = UserOut.model_validate(staff_user).model_copy(
        update={"assigned_conversation_count": counts.get(staff_user.id, 0)}
    )
    return success(out.model_dump(mode="json"))


@router.patch("/{user_id}")
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    staff_user = await service.update_user(db, user_id=user_id, body=body)
    return success(UserOut.model_validate(staff_user).model_dump(mode="json"))
