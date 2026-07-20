from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversations.models import Conversation
from app.customers.models import Customer
from app.feedback.models import CustomerFeedback
from app.notifications import repository as notifications_repository
from app.orchestration.models import ServiceRequest
from app.service_requests.constants import BOOKING_REQUEST_TYPE

_NOT_CLOSED_STATUSES = (
    "open",
    "waiting_for_guest",
    "waiting_for_staff",
    "ai_handling",
    "human_handling",
    "escalated",
)


async def count_conversations_in_range(db: AsyncSession, *, start: datetime, end: datetime) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Conversation)
        .where(Conversation.started_at >= start, Conversation.started_at <= end)
    )
    return result.scalar_one()


async def count_open_conversations(db: AsyncSession) -> int:
    """Current queue state — not range-scoped, since "how many are open
    right now" is a live operational fact, not a historical one."""
    result = await db.execute(
        select(func.count()).select_from(Conversation).where(Conversation.status.in_(_NOT_CLOSED_STATUSES))
    )
    return result.scalar_one()


async def count_escalated_conversations(db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count()).select_from(Conversation).where(Conversation.status == "escalated")
    )
    return result.scalar_one()


async def count_new_customers_in_range(db: AsyncSession, *, start: datetime, end: datetime) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Customer)
        .where(Customer.created_at >= start, Customer.created_at <= end, Customer.deleted_at.is_(None))
    )
    return result.scalar_one()


async def count_booking_enquiries_in_range(db: AsyncSession, *, start: datetime, end: datetime) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(ServiceRequest)
        .where(
            ServiceRequest.request_type == BOOKING_REQUEST_TYPE,
            ServiceRequest.created_at >= start,
            ServiceRequest.created_at <= end,
        )
    )
    return result.scalar_one()


async def feedback_counts_in_range(db: AsyncSession, *, start: datetime, end: datetime) -> tuple[int, int]:
    """Returns (up_count, down_count) for feedback created in range."""
    rows = (
        await db.execute(
            select(CustomerFeedback.rating, func.count())
            .where(CustomerFeedback.created_at >= start, CustomerFeedback.created_at <= end)
            .group_by(CustomerFeedback.rating)
        )
    ).all()
    counts = dict(rows)
    return counts.get("up", 0), counts.get("down", 0)


async def count_unread_notifications(db: AsyncSession) -> int:
    return await notifications_repository.count_unread(db)


async def conversations_by_day(db: AsyncSession, *, start: datetime, end: datetime) -> list[tuple]:
    """Buckets by UTC calendar date of started_at — a deliberate
    simplification (per-resort local-timezone bucketing would need
    resort_settings.timezone applied here) rather than a fabricated
    per-guest-timezone breakdown."""
    result = await db.execute(
        select(func.date(Conversation.started_at), func.count())
        .where(Conversation.started_at >= start, Conversation.started_at <= end)
        .group_by(func.date(Conversation.started_at))
        .order_by(func.date(Conversation.started_at))
    )
    return result.all()


async def bookings_by_status_in_range(db: AsyncSession, *, start: datetime, end: datetime) -> list[tuple]:
    booking_status = func.coalesce(ServiceRequest.details["booking_status"].astext, "pending_review")
    result = await db.execute(
        select(booking_status, func.count())
        .where(
            ServiceRequest.request_type == BOOKING_REQUEST_TYPE,
            ServiceRequest.created_at >= start,
            ServiceRequest.created_at <= end,
        )
        .group_by(booking_status)
    )
    return result.all()
