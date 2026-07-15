import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

_SLUG_ALLOWED = set("abcdefghijklmnopqrstuvwxyz0123456789-")


class TenantCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(min_length=2, max_length=100)

    @field_validator("slug")
    @classmethod
    def _validate_slug(cls, value: str) -> str:
        value = value.lower()
        if not set(value).issubset(_SLUG_ALLOWED):
            raise ValueError("slug may only contain lowercase letters, digits, and hyphens")
        return value


class TenantOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TenantMembershipOut(BaseModel):
    tenant_id: uuid.UUID
    tenant_name: str
    tenant_slug: str
    role: str


class MemberInviteRequest(BaseModel):
    email: EmailStr
    role: str = Field(description="One of: owner, admin, manager, staff, read_only")


class MemberRoleUpdateRequest(BaseModel):
    role: str


class MemberOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    email: str
    role: str
    status: str
    joined_at: datetime | None

    model_config = {"from_attributes": True}
