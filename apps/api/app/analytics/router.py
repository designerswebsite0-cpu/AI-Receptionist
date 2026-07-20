from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics import service
from app.common.responses import success
from app.database import get_db
from app.deps import get_current_user
from app.users.models import User

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/dashboard")
async def get_dashboard_analytics(
    range: str = Query(default="7d"),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    analytics = await service.get_dashboard_analytics(db, range_key=range, start=start, end=end)
    return success(analytics.model_dump(mode="json"))
