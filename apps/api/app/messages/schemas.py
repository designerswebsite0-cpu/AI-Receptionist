import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.messages.constants import ATTACHMENT_TYPES, CONTENT_TYPES, SENDER_TYPES


class AttachmentIn(BaseModel):
    attachment_type: str
    storage_path: str = Field(min_length=1, max_length=1000)
    file_name: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None

    @field_validator("attachment_type")
    @classmethod
    def _validate_type(cls, value: str) -> str:
        if value not in ATTACHMENT_TYPES:
            raise ValueError(f"attachment_type must be one of {ATTACHMENT_TYPES}")
        return value


class AttachmentOut(AttachmentIn):
    id: uuid.UUID
    message_id: uuid.UUID

    model_config = {"from_attributes": True}


class MessageCreateRequest(BaseModel):
    sender_type: str
    content_type: str = "text"
    content_text: str | None = None
    attachments: list[AttachmentIn] = Field(default_factory=list)
    message_metadata: dict = Field(default_factory=dict)
    external_message_id: str | None = None

    @field_validator("sender_type")
    @classmethod
    def _validate_sender_type(cls, value: str) -> str:
        if value not in SENDER_TYPES:
            raise ValueError(f"sender_type must be one of {SENDER_TYPES}")
        return value

    @field_validator("content_type")
    @classmethod
    def _validate_content_type(cls, value: str) -> str:
        if value not in CONTENT_TYPES:
            raise ValueError(f"content_type must be one of {CONTENT_TYPES}")
        return value


class MessageOut(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    direction: str
    sender_type: str
    sender_user_id: uuid.UUID | None
    content_type: str
    content_text: str | None
    delivery_status: str
    read_at: datetime | None
    external_message_id: str | None
    message_metadata: dict
    created_at: datetime
    attachments: list[AttachmentOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}
