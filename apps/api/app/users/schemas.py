import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.users.constants import USER_STATUSES


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None
    avatar_url: str | None
    role: str
    status: str
    last_login_at: datetime | None
    created_at: datetime
    assigned_conversation_count: int = 0

    model_config = {"from_attributes": True}


class UserUpdateRequest(BaseModel):
    """Display-only fields a dashboard admin may edit — never credentials
    or permissions, since neither exists in this deployment's model."""

    full_name: str | None = Field(default=None, max_length=200)
    role: str | None = Field(default=None, max_length=50)
    status: str | None = None

    @field_validator("status")
    @classmethod
    def _v_status(cls, value: str | None) -> str | None:
        if value is not None and value not in USER_STATUSES:
            raise ValueError(f"status must be one of {USER_STATUSES}")
        return value
