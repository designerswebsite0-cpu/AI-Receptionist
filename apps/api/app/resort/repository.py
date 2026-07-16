from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.resort.models import ResortSettings


async def get_resort_settings(db: AsyncSession) -> ResortSettings | None:
    result = await db.execute(select(ResortSettings).limit(1))
    return result.scalar_one_or_none()
