from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog


async def list_audit_logs(
    db: AsyncSession,
    *,
    action: str | None = None,
    resource_type: str | None = None,
    search: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[AuditLog], int]:
    query = select(AuditLog)
    count_query = select(func.count()).select_from(AuditLog)

    conditions = []
    if action:
        conditions.append(AuditLog.action == action)
    if resource_type:
        conditions.append(AuditLog.resource_type == resource_type)
    if search:
        pattern = f"%{search}%"
        conditions.append(
            or_(
                AuditLog.action.ilike(pattern),
                AuditLog.resource_type.ilike(pattern),
                AuditLog.resource_id.ilike(pattern),
            )
        )
    if date_from:
        conditions.append(AuditLog.created_at >= date_from)
    if date_to:
        conditions.append(AuditLog.created_at <= date_to)

    for condition in conditions:
        query = query.where(condition)
        count_query = count_query.where(condition)

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit))
    return list(result.scalars().all()), total
