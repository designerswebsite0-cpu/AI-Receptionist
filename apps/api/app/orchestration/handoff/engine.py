"""Deterministic handoff policy engine — functions.md §28's
evaluate_handoff_requirement / summarize_conversation_for_staff. Every
mandatory scenario is checked here, in code, never left to the LLM's own
judgment (docs/CLAUDE.md "The backend always validates tool requests" —
the same principle applies to handoff decisions).
"""

from app.orchestration.constants import HANDOFF_DEPARTMENTS, HANDOFF_PRIORITIES, MANDATORY_HANDOFF_INTENTS
from app.orchestration.domain import DetectedIntent, HandoffDecision

# (reason_code, priority, department) per mandatory-handoff intent.
_INTENT_HANDOFF_MAPPING: dict[str, tuple[str, str, str]] = {
    "billing_refund": ("refund_request", "high", "billing"),
    "support_emergency": ("safety_incident", "urgent", "security_safety"),
    "support_safety_concern": ("safety_incident", "urgent", "security_safety"),
    "support_medical_concern": ("medical_emergency", "urgent", "security_safety"),
    "support_sensitive_payment_issue": ("payment_failure", "high", "billing"),
    "support_human_agent_request": ("explicit_human_request", "normal", "front_desk"),
    "support_negotiation": ("price_negotiation", "normal", "front_desk"),
    "support_exception_request": ("policy_exception", "normal", "front_desk"),
    "room_cancellation_request": ("cancellation_execution", "normal", "reservations"),
}

_LOW_CONFIDENCE_THRESHOLD = 3
_TOOL_FAILURE_THRESHOLD = 2


def evaluate_handoff_requirement(
    *,
    intent: DetectedIntent,
    consecutive_low_confidence_count: int = 0,
    consecutive_tool_failures: int = 0,
    provider_failed: bool = False,
    tool_signaled_handoff: bool = False,
    tool_handoff_reason: str | None = None,
) -> HandoffDecision:
    """Checked in this exact order — an intent-driven mandatory handoff
    always wins over a soft signal like repeated low confidence, since a
    safety/payment/refund scenario matters more than "the AI is confused."
    """
    if intent.primary_intent in MANDATORY_HANDOFF_INTENTS:
        reason_code, priority, department = _INTENT_HANDOFF_MAPPING.get(
            intent.primary_intent, ("explicit_human_request", "normal", "front_desk")
        )
        return HandoffDecision(
            required=True,
            priority=priority,
            department=department,
            reason_code=reason_code,
            summary=(
                f"Guest intent classified as '{intent.primary_intent}' — always escalated "
                "regardless of confidence."
            ),
        )

    if tool_signaled_handoff:
        return HandoffDecision(
            required=True,
            priority="normal",
            department="front_desk",
            reason_code="explicit_human_request",
            summary=tool_handoff_reason or "Guest explicitly asked to speak with a human.",
        )

    if provider_failed:
        return HandoffDecision(
            required=True,
            priority="high",
            department="front_desk",
            reason_code="provider_failure",
            summary="Both primary and fallback LLM providers failed to respond.",
        )

    if consecutive_tool_failures >= _TOOL_FAILURE_THRESHOLD:
        return HandoffDecision(
            required=True,
            priority="normal",
            department="front_desk",
            reason_code="repeated_tool_failure",
            summary=f"A backend tool failed {consecutive_tool_failures} times in a row for this guest.",
        )

    if consecutive_low_confidence_count >= _LOW_CONFIDENCE_THRESHOLD:
        return HandoffDecision(
            required=True,
            priority="normal",
            department="front_desk",
            reason_code="repeated_low_confidence",
            summary=(
                f"Intent could not be confidently classified {consecutive_low_confidence_count} "
                "turns in a row — the AI may be misunderstanding this guest."
            ),
        )

    return HandoffDecision(required=False)


def summarize_conversation_for_staff(
    *, guest_message: str, intent: DetectedIntent, entities: dict, handoff: HandoffDecision
) -> str:
    entity_summary = ", ".join(f"{key}={value}" for key, value in entities.items()) or "none captured"
    return (
        f"Reason: {handoff.reason_code or 'unspecified'} (priority: {handoff.priority}, "
        f"department: {handoff.department or 'unassigned'}).\n"
        f"Last guest message: \"{guest_message}\"\n"
        f"Detected intent: {intent.primary_intent} (confidence {intent.confidence:.2f}).\n"
        f"Known details: {entity_summary}."
    )


assert set(HANDOFF_PRIORITIES) and set(HANDOFF_DEPARTMENTS)  # both taxonomies must be non-empty
