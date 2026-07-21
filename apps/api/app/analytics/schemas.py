from datetime import date, datetime

from pydantic import BaseModel


class DashboardSummaryOut(BaseModel):
    range_start: datetime
    range_end: datetime
    total_conversations: int
    open_conversations: int
    escalated_conversations: int
    new_customers: int
    booking_enquiries: int
    feedback_total: int
    feedback_positive_rate: float | None
    unread_notifications: int
    avg_messages_per_conversation: float | None
    handoff_rate: float | None


class DailyCountOut(BaseModel):
    day: date
    count: int


class CategoryCountOut(BaseModel):
    label: str
    count: int


class DashboardAnalyticsOut(BaseModel):
    summary: DashboardSummaryOut
    conversations_by_day: list[DailyCountOut]
    bookings_by_status: list[CategoryCountOut]
    feedback_by_rating: list[CategoryCountOut]
    conversations_by_status: list[CategoryCountOut]
    conversations_by_channel: list[CategoryCountOut]
    staff_workload: list[CategoryCountOut]
