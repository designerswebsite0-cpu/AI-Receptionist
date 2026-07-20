import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.feedback.constants import FEEDBACK_STATUSES


class FeedbackOut(BaseModel):
    id: uuid.UUID
    category: str
    rating: str
    comment: str | None
    conversation_id: uuid.UUID | None
    customer_id: uuid.UUID | None
    customer_name: str | None = None
    status: str
    assigned_agent_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class FeedbackUpdateRequest(BaseModel):
    status: str | None = None
    assigned_agent_id: uuid.UUID | None = None

    @field_validator("status")
    @classmethod
    def _v_status(cls, value: str | None) -> str | None:
        if value is not None and value not in FEEDBACK_STATUSES:
            raise ValueError(f"status must be one of {FEEDBACK_STATUSES}")
        return value


class FeedbackStatsOut(BaseModel):
    total: int
    up_count: int
    down_count: int
    positive_rate: float | None
    by_category: dict[str, int]
