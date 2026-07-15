from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import success
from app.database import get_db

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def liveness() -> dict:
    """Liveness probe — process is up. No dependency checks."""
    return success({"status": "ok"})


@router.get("/readyz")
async def readiness(db: AsyncSession = Depends(get_db)) -> dict:
    """Readiness probe — verifies the database is reachable."""
    await db.execute(text("SELECT 1"))
    return success({"status": "ready"})
