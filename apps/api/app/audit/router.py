from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import repository
from app.common.pagination import PageParams, build_page_meta
from app.common.responses import success
from app.database import get_db
from app.deps import get_current_user
from app.users import repository as users_repository
from app.users.models import User

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("/logs")
async def list_audit_logs(
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    search: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    params = PageParams(page=page, page_size=page_size)
    logs, total = await repository.list_audit_logs(
        db,
        action=action,
        resource_type=resource_type,
        search=search,
        date_from=date_from,
        date_to=date_to,
        offset=params.offset,
        limit=params.page_size,
    )
    actor_ids = [log.actor_user_id for log in logs if log.actor_user_id]
    names = await users_repository.get_names_by_ids(db, actor_ids)

    items = [
        {
            "id": str(log.id),
            "actor_user_id": str(log.actor_user_id) if log.actor_user_id else None,
            "actor_name": names.get(log.actor_user_id) if log.actor_user_id else None,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "before_state": log.before_state,
            "after_state": log.after_state,
            "event_metadata": log.event_metadata,
            "ip_address": str(log.ip_address) if log.ip_address else None,
            "correlation_id": log.correlation_id,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]
    return success({"items": items, "meta": build_page_meta(params, total).model_dump()})
