from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import success
from app.database import get_db
from app.deps import get_current_user
from app.health import service
from app.users.models import User

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


@router.get("/api/v1/health/integrations")
async def integrations_status(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    """Settings > Integrations (Phase X Stage 8) — masked identifiers only,
    never a raw secret. Staff-only, unlike the public /healthz probe."""
    return success(await service.get_integrations_status(db))


@router.get("/api/v1/health/system")
async def system_status(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    """Settings > System Monitoring (Phase X Stage 8) — aggregated status
    only, never a stack trace or env var."""
    return success(await service.get_system_status(db))
