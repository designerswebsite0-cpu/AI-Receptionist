from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "bearer"


class TenantMembershipOut(BaseModel):
    tenant_id: str
    tenant_name: str
    role: str


class CurrentUserOut(BaseModel):
    user_id: str
    email: str | None
    memberships: list[TenantMembershipOut]
