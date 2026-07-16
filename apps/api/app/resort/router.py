from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import success
from app.database import get_db
from app.deps import get_current_user
from app.resort import service
from app.resort.schemas import ResortSettingsCreateRequest, ResortSettingsOut, ResortSettingsUpdateRequest
from app.users.models import User

router = APIRouter(prefix="/api/v1/resort", tags=["resort"])


@router.post("/settings")
async def create_resort_settings(
    body: ResortSettingsCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    settings_row = await service.create_resort_settings(db, body=body, actor_user_id=user.id)
    return success(ResortSettingsOut.model_validate(settings_row).model_dump(mode="json"))


@router.get("/settings")
async def get_resort_settings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    settings_row = await service.get_resort_settings_or_404(db)
    return success(ResortSettingsOut.model_validate(settings_row).model_dump(mode="json"))


@router.patch("/settings")
async def update_resort_settings(
    body: ResortSettingsUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    settings_row = await service.update_resort_settings(db, body=body, actor_user_id=user.id)
    return success(ResortSettingsOut.model_validate(settings_row).model_dump(mode="json"))
