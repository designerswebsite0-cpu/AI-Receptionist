from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bookings.models import RoomBooking
from app.conversations.models import Conversation
from app.customers.models import Customer
from app.feedback.models import CustomerFeedback
from app.messages.models import Message
from app.notifications import repository as notifications_repository
from app.orchestration.models import OrchestrationTurn
from app.users.models import User

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
        .select_from(RoomBooking)
        .where(RoomBooking.created_at >= start, RoomBooking.created_at <= end)
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


async def conversations_by_status_in_range(db: AsyncSession, *, start: datetime, end: datetime) -> list[tuple]:
    result = await db.execute(
        select(Conversation.status, func.count())
        .where(Conversation.started_at >= start, Conversation.started_at <= end)
        .group_by(Conversation.status)
    )
    return result.all()


async def conversations_by_channel_in_range(db: AsyncSession, *, start: datetime, end: datetime) -> list[tuple]:
    result = await db.execute(
        select(Conversation.channel, func.count())
        .where(Conversation.started_at >= start, Conversation.started_at <= end)
        .group_by(Conversation.channel)
    )
    return result.all()


async def avg_messages_per_conversation_in_range(db: AsyncSession, *, start: datetime, end: datetime) -> float | None:
    result = await db.execute(
        select(func.count(Message.id), func.count(func.distinct(Message.conversation_id)))
        .select_from(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(Conversation.started_at >= start, Conversation.started_at <= end)
    )
    message_count, conversation_count = result.one()
    return (message_count / conversation_count) if conversation_count else None


async def handoff_rate_in_range(db: AsyncSession, *, start: datetime, end: datetime) -> float | None:
    """Fraction of conversations in range where at least one turn signaled
    handoff_required — a real AI-performance signal (how often the AI
    couldn't safely continue on its own), not a fabricated satisfaction
    score."""
    total = await count_conversations_in_range(db, start=start, end=end)
    if not total:
        return None
    result = await db.execute(
        select(func.count(func.distinct(OrchestrationTurn.conversation_id)))
        .select_from(OrchestrationTurn)
        .join(Conversation, Conversation.id == OrchestrationTurn.conversation_id)
        .where(
            Conversation.started_at >= start,
            Conversation.started_at <= end,
            OrchestrationTurn.handoff_required.is_(True),
        )
    )
    handed_off = result.scalar_one()
    return handed_off / total


async def staff_workload(db: AsyncSession, *, limit: int = 10) -> list[tuple]:
    """Current open-conversation count per staff member — a live
    operational fact (who's carrying load right now), not range-scoped."""
    result = await db.execute(
        select(func.coalesce(User.full_name, User.email), func.count())
        .select_from(Conversation)
        .join(User, User.id == Conversation.assigned_agent_id)
        .where(Conversation.status.in_(_NOT_CLOSED_STATUSES))
        .group_by(User.id, User.full_name, User.email)
        .order_by(func.count().desc())
        .limit(limit)
    )
    return result.all()


async def bookings_by_status_in_range(db: AsyncSession, *, start: datetime, end: datetime) -> list[tuple]:
    result = await db.execute(
        select(RoomBooking.status, func.count())
        .where(RoomBooking.created_at >= start, RoomBooking.created_at <= end)
        .group_by(RoomBooking.status)
    )
    return result.all()
