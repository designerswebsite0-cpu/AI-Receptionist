import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.orchestration.constants import HANDOFF_DEPARTMENTS, HANDOFF_PRIORITIES


class ProcessMessageRequest(BaseModel):
    message_id: uuid.UUID
    channel: str = "webchat"


class ProviderUsageOut(BaseModel):
    provider: str
    model: str
    latency_ms: int
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class HandoffDecisionOut(BaseModel):
    required: bool
    priority: str = "normal"
    department: str | None = None
    reason_code: str | None = None
    summary: str | None = None


class ProcessMessageResponse(BaseModel):
    """The channel-neutral pipeline outcome — deliberately does not include
    any chain-of-thought, only the operational decision summary (same
    principle as OrchestrationTurn itself)."""

    conversation_id: uuid.UUID
    response_text: str | None
    intent: str
    intent_confidence: float
    missing_information: list[str]
    flow_state: str | None
    handoff: HandoffDecisionOut
    validation_passed: bool
    provider_usage: ProviderUsageOut | None
    error_code: str | None = None


class ConversationStateOut(BaseModel):
    conversation_id: uuid.UUID
    current_state: str
    flow_state: str | None
    status: str
    ai_active: bool
    human_active: bool
    last_intent: str | None
    last_intent_confidence: float | None


class TurnCitationOut(BaseModel):
    chunk_id: uuid.UUID
    source_title: str
    source_priority: str
    authoritative: bool
    score: float


class OrchestrationTurnOut(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    message_id: uuid.UUID | None
    response_message_id: uuid.UUID | None
    detected_intent: str | None
    intent_confidence: float | None
    flow_state: str | None
    tool_name: str | None
    tool_status: str | None
    handoff_required: bool
    handoff_reason: str | None
    handoff_priority: str | None
    handoff_department: str | None
    provider_used: str | None
    model_used: str | None
    latency_ms: int | None
    error_code: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ForceHandoffRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
    department: str = "front_desk"
    priority: str = "normal"

    @field_validator("department")
    @classmethod
    def _validate_department(cls, value: str) -> str:
        if value not in HANDOFF_DEPARTMENTS:
            raise ValueError(f"department must be one of {HANDOFF_DEPARTMENTS}")
        return value

    @field_validator("priority")
    @classmethod
    def _validate_priority(cls, value: str) -> str:
        if value not in HANDOFF_PRIORITIES:
            raise ValueError(f"priority must be one of {HANDOFF_PRIORITIES}")
        return value


class ProviderHealthOut(BaseModel):
    llm_configured: bool
    llm_fallback_configured: bool
    embedding_configured: bool
