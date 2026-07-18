"""Pre-send response validation. Deterministic pattern checks, run
against every AI-generated response before it becomes a Message row —
mirrors app.orchestration.tools.validation's "backend decides, the model
requests" principle applied to the final text instead of a tool call.

Deliberately does not call a second LLM to judge the first LLM's output
(no LLM-judge in this phase, consistent with the benchmark runner's own
no-LLM-judge design) — these are pattern-matching guardrails, not a
semantic correctness check. Genuine semantic mismatches (a citation that
technically exists but doesn't really support the claim) are NOT caught
here; this is an honest limitation, not silently pretended coverage.
"""

from app.orchestration.domain import (
    MissingInformation,
    RetrievedContext,
    ToolDecision,
    ValidationIssue,
    ValidationResult,
)

_BOOKING_CONFIRMATION_PHRASES = (
    "booking is confirmed", "your booking has been confirmed", "reservation is confirmed",
    "you're all set", "all set for your stay", "booking confirmed",
)
_PAYMENT_CONFIRMATION_PHRASES = (
    "payment has been processed", "payment received", "payment successful",
    "refund has been processed", "refund is on its way", "refund has been issued", "refund processed",
)
_SYSTEM_PROMPT_LEAK_PHRASES = (
    "my system prompt", "my instructions are", "i was told to", "as an ai language model my instructions",
    "the system prompt says", "my internal instructions",
)
_PRICE_KEYWORDS = ("inr ", "₹", "$", " usd", "price is", "costs ", "rate is", "priced at")
_AVAILABILITY_KEYWORDS = ("is available", "we have availability", "rooms are available", "is in stock", "we have rooms")

_MAX_LENGTH_BY_CHANNEL = {"whatsapp": 400, "webchat": 1500}
_DEFAULT_MAX_LENGTH = 1500


def _mentions_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def validate_response(
    *,
    response_text: str,
    tool_decision: ToolDecision,
    retrieved_context: RetrievedContext,
    missing_information: MissingInformation,
    channel: str = "webchat",
) -> ValidationResult:
    issues: list[ValidationIssue] = []
    lowered = response_text.lower()

    if _mentions_any(lowered, _BOOKING_CONFIRMATION_PHRASES):
        booking_tool_succeeded = tool_decision.status == "success" and (
            tool_decision.tool_name and "booking" in tool_decision.tool_name
        )
        if not booking_tool_succeeded:
            issues.append(
                ValidationIssue(
                    code="unauthorized_booking_confirmation",
                    message="Response claims a booking is confirmed without a successful booking tool result.",
                    severity="blocking",
                )
            )

    if _mentions_any(lowered, _PAYMENT_CONFIRMATION_PHRASES):
        issues.append(
            ValidationIssue(
                code="unauthorized_payment_claim",
                message="Response claims a payment/refund was processed — no tool in this system confirms that.",
                severity="blocking",
            )
        )

    if _mentions_any(lowered, _SYSTEM_PROMPT_LEAK_PHRASES):
        issues.append(
            ValidationIssue(
                code="system_prompt_exposure",
                message="Response appears to reveal internal system instructions.",
                severity="blocking",
            )
        )

    mentions_price = _mentions_any(lowered, _PRICE_KEYWORDS)
    mentions_availability = _mentions_any(lowered, _AVAILABILITY_KEYWORDS)
    if (mentions_price or mentions_availability) and retrieved_context.is_empty:
        issues.append(
            ValidationIssue(
                code="unsupported_factual_claim",
                message="Response makes a price/availability claim with no retrieved knowledge to support it.",
                severity="blocking",
            )
        )

    if missing_information.has_gaps and "?" not in response_text:
        issues.append(
            ValidationIssue(
                code="missing_followup_question",
                message="Required information is still missing but the response doesn't ask for it.",
                severity="warning",
            )
        )

    max_length = _MAX_LENGTH_BY_CHANNEL.get(channel, _DEFAULT_MAX_LENGTH)
    if len(response_text) > max_length:
        issues.append(
            ValidationIssue(
                code="excessive_verbosity",
                message=f"Response is {len(response_text)} chars, exceeding the {max_length}-char guideline.",
                severity="warning",
            )
        )

    passed = not any(issue.severity == "blocking" for issue in issues)
    return ValidationResult(passed=passed, issues=issues)


def safe_fallback_response() -> str:
    """Returned in place of a blocked response — never silently drops the
    guest's message unanswered, and never repeats whatever unsafe claim
    was caught."""
    return (
        "I want to make sure I give you completely accurate information on this — let me "
        "connect you with a member of our team who can confirm the details."
    )
