"""Orchestration domain model — internal dataclasses passed between
pipeline stages. Deliberately not Pydantic: these never cross a process
boundary (app.orchestration.schemas is the Pydantic API surface); plain
dataclasses keep construction cheap inside a single request's pipeline
run.

No chain-of-thought is ever stored here. Every field is an operationally
useful decision summary (what was decided, not the model's reasoning
trace) — see docs/phase-4/PHASE_4_IMPLEMENTATION_PLAN.md §2's
orchestration_turns schema, which this maps onto directly.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ConversationInput:
    conversation_id: uuid.UUID
    customer_id: uuid.UUID
    message_id: uuid.UUID
    message_text: str
    channel: str
    language: str = "en"


@dataclass
class DetectedIntent:
    primary_intent: str
    confidence: float
    secondary_intents: list[tuple[str, float]] = field(default_factory=list)
    is_small_talk: bool = False

    @property
    def all_intents(self) -> list[str]:
        return [self.primary_intent] + [intent for intent, _ in self.secondary_intents]


@dataclass
class ExtractedEntities:
    values: dict[str, object] = field(default_factory=dict)
    confidence: dict[str, float] = field(default_factory=dict)
    source: dict[str, str] = field(default_factory=dict)  # field -> "deterministic" | "llm"

    def get(self, field_name: str, default=None):
        return self.values.get(field_name, default)


@dataclass
class MissingInformation:
    required_fields: list[str] = field(default_factory=list)
    prompt: str | None = None  # the follow-up question to ask, if any

    @property
    def has_gaps(self) -> bool:
        return bool(self.required_fields)


@dataclass
class RetrievedCitation:
    chunk_id: uuid.UUID
    content: str
    source_title: str
    source_priority: str
    authoritative: bool
    score: float
    source_url: str | None = None


@dataclass
class RetrievedContext:
    query: str
    citations: list[RetrievedCitation] = field(default_factory=list)
    classification: str = "general"
    latency_ms: int = 0

    @property
    def is_empty(self) -> bool:
        return not self.citations


@dataclass
class ToolDecision:
    tool_name: str | None
    tool_input: dict = field(default_factory=dict)
    decision: str = "none"  # "none" | "execute" | "needs_guest_confirmation" | "needs_staff_approval" | "denied"
    denial_reason: str | None = None
    output: dict | None = None
    status: str | None = None  # "success" | "failed" | None (not attempted)


@dataclass
class HandoffDecision:
    required: bool
    priority: str = "normal"
    department: str | None = None
    reason_code: str | None = None
    summary: str | None = None
    outstanding_action: str | None = None
    suggested_staff_response: str | None = None


@dataclass
class ValidationIssue:
    code: str
    message: str
    severity: str  # "warning" | "blocking"


@dataclass
class ValidationResult:
    passed: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    rewritten_text: str | None = None

    @property
    def blocked(self) -> bool:
        return any(issue.severity == "blocking" for issue in self.issues)


@dataclass
class ProviderUsage:
    provider: str
    model: str
    latency_ms: int
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


@dataclass
class OrchestrationResult:
    conversation_id: uuid.UUID
    response_text: str | None
    intent: DetectedIntent
    entities: ExtractedEntities
    missing_information: MissingInformation
    retrieved_context: RetrievedContext
    flow_state: str | None
    tool_decision: ToolDecision
    handoff_decision: HandoffDecision
    validation_result: ValidationResult
    provider_usage: ProviderUsage | None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
