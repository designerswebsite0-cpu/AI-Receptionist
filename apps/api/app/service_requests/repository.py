from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.orchestration.models import ServiceRequest
from app.service_requests.constants import BOOKING_REQUEST_TYPE


async def list_booking_requests(
    db: AsyncSession,
    *,
    status: str | None = None,
    booking_status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[ServiceRequest], int]:
    query = select(ServiceRequest).where(ServiceRequest.request_type == BOOKING_REQUEST_TYPE)
    count_query = (
        select(func.count()).select_from(ServiceRequest).where(ServiceRequest.request_type == BOOKING_REQUEST_TYPE)
    )

    if status:
        query = query.where(ServiceRequest.status == status)
        count_query = count_query.where(ServiceRequest.status == status)
    if booking_status:
        condition = ServiceRequest.details["booking_status"].astext == booking_status
        query = query.where(condition)
        count_query = count_query.where(condition)

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(query.order_by(ServiceRequest.created_at.desc()).offset(offset).limit(limit))
    return list(result.scalars().all()), total
