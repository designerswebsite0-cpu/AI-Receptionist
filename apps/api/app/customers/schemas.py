import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.customers.models import CONTACT_TYPES


class ContactIn(BaseModel):
    contact_type: str
    value: str = Field(min_length=1, max_length=320)
    is_primary: bool = False
    verified: bool = False

    @field_validator("contact_type")
    @classmethod
    def _validate_contact_type(cls, value: str) -> str:
        if value not in CONTACT_TYPES:
            raise ValueError(f"contact_type must be one of {CONTACT_TYPES}")
        return value


class ContactOut(ContactIn):
    id: uuid.UUID
    customer_id: uuid.UUID

    model_config = {"from_attributes": True}


class CustomerCreateRequest(BaseModel):
    full_name: str | None = None
    preferred_language: str = "en"
    preferred_channel: str | None = None
    contacts: list[ContactIn] = Field(default_factory=list)


class CustomerUpdateRequest(BaseModel):
    full_name: str | None = None
    preferred_language: str | None = None
    preferred_channel: str | None = None
    loyalty_reference: str | None = None
    preferences: dict | None = None
    resort_preferences: dict | None = None


class CustomerOut(BaseModel):
    id: uuid.UUID
    full_name: str | None
    preferred_language: str
    preferred_channel: str | None
    lifetime_value: float
    loyalty_reference: str | None
    preferences: dict
    resort_preferences: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class NoteCreateRequest(BaseModel):
    note: str = Field(min_length=1, max_length=4000)


class NoteOut(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    author_user_id: uuid.UUID | None
    note: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TagCreateRequest(BaseModel):
    tag: str = Field(min_length=1, max_length=50)
