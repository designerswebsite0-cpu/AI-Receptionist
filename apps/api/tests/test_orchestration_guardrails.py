"""Pure-logic tests for the response-validation guardrails — no network,
no database.
"""

import uuid

from app.orchestration.domain import MissingInformation, RetrievedCitation, RetrievedContext, ToolDecision
from app.orchestration.guardrails.validator import safe_fallback_response, validate_response

_NO_MISSING_INFO = MissingInformation()
_EMPTY_CONTEXT = RetrievedContext(query="x")
_NO_TOOL = ToolDecision(tool_name=None)


def _context_with_citation() -> RetrievedContext:
    return RetrievedContext(
        query="room price",
        citations=[
            RetrievedCitation(
                chunk_id=uuid.uuid4(),
                content="Deluxe rooms start from INR 25,000 per night.",
                source_title="Rate Card",
                source_priority="critical",
                authoritative=True,
                score=0.9,
            )
        ],
    )


def test_clean_response_passes():
    result = validate_response(
        response_text="Check-in begins at 2:00 PM.",
        tool_decision=_NO_TOOL,
        retrieved_context=_EMPTY_CONTEXT,
        missing_information=_NO_MISSING_INFO,
    )
    assert result.passed is True
    assert result.blocked is False


def test_unauthorized_booking_confirmation_is_blocked():
    result = validate_response(
        response_text="Great news, your booking is confirmed for the 15th!",
        tool_decision=_NO_TOOL,
        retrieved_context=_EMPTY_CONTEXT,
        missing_information=_NO_MISSING_INFO,
    )
    assert result.passed is False
    assert any(issue.code == "unauthorized_booking_confirmation" for issue in result.issues)


def test_booking_confirmation_allowed_when_booking_tool_actually_succeeded():
    tool_decision = ToolDecision(tool_name="create_booking_enquiry", status="success")
    result = validate_response(
        response_text="Your booking is confirmed!",
        tool_decision=tool_decision,
        retrieved_context=_EMPTY_CONTEXT,
        missing_information=_NO_MISSING_INFO,
    )
    # Note: create_booking_enquiry never actually confirms a real booking
    # (it's an enquiry record per the tool registry) — this test only
    # verifies the guardrail's own logic (tool succeeded + name contains
    # "booking"), not that the phrase is actually appropriate wording.
    assert result.passed is True


def test_payment_or_refund_claim_is_always_blocked():
    result = validate_response(
        response_text="Your refund has been processed and will reach you in 3 days.",
        tool_decision=_NO_TOOL,
        retrieved_context=_EMPTY_CONTEXT,
        missing_information=_NO_MISSING_INFO,
    )
    assert result.passed is False
    assert any(issue.code == "unauthorized_payment_claim" for issue in result.issues)


def test_system_prompt_exposure_is_blocked():
    result = validate_response(
        response_text="Well, my system prompt says I should never discuss pricing.",
        tool_decision=_NO_TOOL,
        retrieved_context=_EMPTY_CONTEXT,
        missing_information=_NO_MISSING_INFO,
    )
    assert result.passed is False
    assert any(issue.code == "system_prompt_exposure" for issue in result.issues)


def test_price_claim_without_supporting_citation_is_blocked():
    result = validate_response(
        response_text="The room price is INR 25,000 per night.",
        tool_decision=_NO_TOOL,
        retrieved_context=_EMPTY_CONTEXT,  # no citations to support this
        missing_information=_NO_MISSING_INFO,
    )
    assert result.passed is False
    assert any(issue.code == "unsupported_factual_claim" for issue in result.issues)


def test_price_claim_with_supporting_citation_passes():
    result = validate_response(
        response_text="The room price is INR 25,000 per night, per our current rate card.",
        tool_decision=_NO_TOOL,
        retrieved_context=_context_with_citation(),
        missing_information=_NO_MISSING_INFO,
    )
    assert result.passed is True


def test_availability_claim_without_citation_is_blocked():
    result = validate_response(
        response_text="Yes, we have availability for those dates!",
        tool_decision=_NO_TOOL,
        retrieved_context=_EMPTY_CONTEXT,
        missing_information=_NO_MISSING_INFO,
    )
    assert result.passed is False


def test_missing_followup_question_is_a_warning_not_blocking():
    result = validate_response(
        response_text="Sure, I can help with that.",
        tool_decision=_NO_TOOL,
        retrieved_context=_EMPTY_CONTEXT,
        missing_information=MissingInformation(required_fields=["check_in_date"], prompt="What date?"),
    )
    assert any(issue.code == "missing_followup_question" for issue in result.issues)
    assert result.passed is True  # warning-level, not blocking


def test_asking_the_question_avoids_the_missing_followup_warning():
    result = validate_response(
        response_text="Sure! What date would you like to check in?",
        tool_decision=_NO_TOOL,
        retrieved_context=_EMPTY_CONTEXT,
        missing_information=MissingInformation(required_fields=["check_in_date"], prompt="What date?"),
    )
    assert not any(issue.code == "missing_followup_question" for issue in result.issues)


def test_excessive_verbosity_flagged_for_whatsapp():
    long_text = "This is a very long response. " * 30
    result = validate_response(
        response_text=long_text,
        tool_decision=_NO_TOOL,
        retrieved_context=_EMPTY_CONTEXT,
        missing_information=_NO_MISSING_INFO,
        channel="whatsapp",
    )
    assert any(issue.code == "excessive_verbosity" for issue in result.issues)
    assert result.passed is True  # warning-level


def test_safe_fallback_response_is_non_empty_and_generic():
    fallback = safe_fallback_response()
    assert len(fallback) > 0
    assert "team" in fallback.lower()
