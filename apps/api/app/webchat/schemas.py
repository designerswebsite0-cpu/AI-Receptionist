import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.webchat.constants import RATING_VALUES


class WebchatSessionOut(BaseModel):
    session_id: uuid.UUID
    conversation_id: uuid.UUID
    # Only populated once, in the response body of session creation — the
    # caller (the website's own Next.js server, or a direct browser client
    # in a same-origin deployment) is responsible for storing it as an
    # HttpOnly cookie. Never re-sent on session restoration.
    token: str | None = None
    expires_at: datetime
    current_state: str
    flow_state: str | None
    status: str
    ai_active: bool
    human_active: bool


class WebchatMessageIn(BaseModel):
    message: str = Field(min_length=1)
    # Client-generated idempotency key (e.g. a UUID minted before the fetch
    # call) — lets a rapid double-click or a retried request be recognized
    # as the same send instead of creating a duplicate guest message.
    client_message_id: str | None = Field(default=None, max_length=100)

    @field_validator("message")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("message must not be blank")
        return stripped


class WebchatCitationOut(BaseModel):
    """Guest-safe citation shape — deliberately narrower than
    app.orchestration.schemas.TurnCitationOut: no chunk_id (internal
    identifier) and no relevance score (an internal ranking signal, not
    guest-meaningful information)."""

    source_title: str
    source_priority: str
    authoritative: bool


class WebchatHandoffOut(BaseModel):
    required: bool
    status: str  # "none" | "requested" | "active"
    department: str | None = None


class WebchatMessageOut(BaseModel):
    message_id: uuid.UUID | None
    response_text: str | None
    citations: list[WebchatCitationOut] = Field(default_factory=list)
    handoff: WebchatHandoffOut
    ai_active: bool
    human_active: bool
    flow_state: str | None
    error_code: str | None = None


class WebchatTranscriptMessageOut(BaseModel):
    id: uuid.UUID
    sender_type: str
    content_text: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class WebchatHandoffRequest(BaseModel):
    reason: str = Field(default="Guest requested a staff member.", max_length=500)


class WebchatFeedbackIn(BaseModel):
    turn_id: uuid.UUID | None = None
    rating: str
    comment: str | None = Field(default=None, max_length=500)

    @field_validator("rating")
    @classmethod
    def _validate_rating(cls, value: str) -> str:
        if value not in RATING_VALUES:
            raise ValueError(f"rating must be one of {RATING_VALUES}")
        return value


class WebchatContactIn(BaseModel):
    """Optional contact capture (brief §8) — validated/normalized here,
    never blindly trusted. At least one of phone/email is required; the
    service layer never reveals whether a value already belongs to an
    existing customer (see app.webchat.service.capture_contact)."""

    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=32)
    email: EmailStr | None = None
    marketing_consent: bool = False

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        import re

        if not re.fullmatch(r"\+?[0-9\s-]{7,20}", value):
            raise ValueError("Invalid phone number")
        return value.strip()

    @model_validator(mode="after")
    def _require_a_contact_method(self) -> "WebchatContactIn":
        if not self.phone and not self.email:
            raise ValueError("At least one of phone or email is required")
        return self
