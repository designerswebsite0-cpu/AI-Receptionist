import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.conversations.constants import CHANNELS, DIALOGUE_STATES, PRIORITIES, STATUSES


class ConversationCreateRequest(BaseModel):
    customer_id: uuid.UUID
    channel: str
    priority: str = "normal"
    conversation_metadata: dict = Field(default_factory=dict)

    @field_validator("channel")
    @classmethod
    def _validate_channel(cls, value: str) -> str:
        if value not in CHANNELS:
            raise ValueError(f"channel must be one of {CHANNELS}")
        return value

    @field_validator("priority")
    @classmethod
    def _validate_priority(cls, value: str) -> str:
        if value not in PRIORITIES:
            raise ValueError(f"priority must be one of {PRIORITIES}")
        return value


class ConversationUpdateRequest(BaseModel):
    priority: str | None = None
    summary: str | None = None
    tags: list[str] | None = None

    @field_validator("priority")
    @classmethod
    def _validate_priority(cls, value: str | None) -> str | None:
        if value is not None and value not in PRIORITIES:
            raise ValueError(f"priority must be one of {PRIORITIES}")
        return value


class StatusChangeRequest(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def _validate_status(cls, value: str) -> str:
        if value not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        return value


class StateChangeRequest(BaseModel):
    state: str
    changed_by: str = "human"
    metadata: dict = Field(default_factory=dict)

    @field_validator("state")
    @classmethod
    def _validate_state(cls, value: str) -> str:
        if value not in DIALOGUE_STATES:
            raise ValueError(f"state must be one of {DIALOGUE_STATES}")
        return value


class AssignRequest(BaseModel):
    agent_user_id: uuid.UUID


class ConversationOut(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    channel: str
    status: str
    current_state: str
    assigned_agent_id: uuid.UUID | None
    priority: str
    started_at: datetime
    last_message_at: datetime | None
    closed_at: datetime | None
    ai_active: bool
    human_active: bool
    summary: str | None
    tags: list[str]
    conversation_metadata: dict

    model_config = {"from_attributes": True}
