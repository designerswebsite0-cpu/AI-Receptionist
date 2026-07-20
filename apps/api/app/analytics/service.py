"""Dashboard & Analytics home (Phase X Stage 9): every number here comes
from a real aggregation over existing tables — no invented metrics, no
fabricated trend lines. See app/analytics/repository.py for the queries.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics import repository
from app.analytics.schemas import CategoryCountOut, DailyCountOut, DashboardAnalyticsOut, DashboardSummaryOut
from app.errors import ValidationErrorApp

VALID_RANGES = ("today", "7d", "30d", "custom")


def resolve_range(
    range_key: str, start: datetime | None, end: datetime | None
) -> tuple[datetime, datetime]:
    if range_key not in VALID_RANGES:
        raise ValidationErrorApp(f"range must be one of {VALID_RANGES}")

    now = datetime.now(UTC)
    if range_key == "custom":
        if start is None or end is None:
            raise ValidationErrorApp("start and end are required when range=custom")
        if start > end:
            raise ValidationErrorApp("start must be before end")
        return start, end
    if range_key == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0), now
    days = 7 if range_key == "7d" else 30
    return now - timedelta(days=days), now


async def get_dashboard_analytics(
    db: AsyncSession, *, range_key: str, start: datetime | None, end: datetime | None
) -> DashboardAnalyticsOut:
    range_start, range_end = resolve_range(range_key, start, end)

    total_conversations = await repository.count_conversations_in_range(db, start=range_start, end=range_end)
    open_conversations = await repository.count_open_conversations(db)
    escalated_conversations = await repository.count_escalated_conversations(db)
    new_customers = await repository.count_new_customers_in_range(db, start=range_start, end=range_end)
    booking_enquiries = await repository.count_booking_enquiries_in_range(db, start=range_start, end=range_end)
    up_count, down_count = await repository.feedback_counts_in_range(db, start=range_start, end=range_end)
    unread_notifications = await repository.count_unread_notifications(db)

    feedback_total = up_count + down_count
    positive_rate = (up_count / feedback_total) if feedback_total else None

    conversations_by_day_rows = await repository.conversations_by_day(db, start=range_start, end=range_end)
    bookings_by_status_rows = await repository.bookings_by_status_in_range(db, start=range_start, end=range_end)

    summary = DashboardSummaryOut(
        range_start=range_start,
        range_end=range_end,
        total_conversations=total_conversations,
        open_conversations=open_conversations,
        escalated_conversations=escalated_conversations,
        new_customers=new_customers,
        booking_enquiries=booking_enquiries,
        feedback_total=feedback_total,
        feedback_positive_rate=positive_rate,
        unread_notifications=unread_notifications,
    )

    return DashboardAnalyticsOut(
        summary=summary,
        conversations_by_day=[DailyCountOut(day=row[0], count=row[1]) for row in conversations_by_day_rows],
        bookings_by_status=[CategoryCountOut(label=row[0], count=row[1]) for row in bookings_by_status_rows],
        feedback_by_rating=[
            CategoryCountOut(label="up", count=up_count),
            CategoryCountOut(label="down", count=down_count),
        ],
    )
