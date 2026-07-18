"""Pure-logic tests for the deterministic handoff policy engine — no
network, no database. Every mandatory-handoff scenario from the Phase 4
brief that maps onto a taxonomy intent is checked explicitly.
"""

import pytest

from app.orchestration.constants import MANDATORY_HANDOFF_INTENTS
from app.orchestration.domain import DetectedIntent
from app.orchestration.handoff.engine import evaluate_handoff_requirement, summarize_conversation_for_staff


def _intent(name: str, confidence: float = 0.9) -> DetectedIntent:
    return DetectedIntent(primary_intent=name, confidence=confidence)


@pytest.mark.parametrize("intent_name", MANDATORY_HANDOFF_INTENTS)
def test_every_mandatory_handoff_intent_triggers_required_handoff(intent_name):
    decision = evaluate_handoff_requirement(intent=_intent(intent_name))
    assert decision.required is True
    assert decision.reason_code is not None
    assert decision.priority in ("low", "normal", "high", "urgent")


def test_ordinary_intent_does_not_trigger_handoff():
    decision = evaluate_handoff_requirement(intent=_intent("general_checkin_checkout"))
    assert decision.required is False


def test_medical_emergency_is_urgent_priority_to_security_safety():
    decision = evaluate_handoff_requirement(intent=_intent("support_medical_concern"))
    assert decision.priority == "urgent"
    assert decision.department == "security_safety"


def test_refund_request_routes_to_billing():
    decision = evaluate_handoff_requirement(intent=_intent("billing_refund"))
    assert decision.department == "billing"
    assert decision.reason_code == "refund_request"


def test_mandatory_intent_wins_over_a_tool_signal():
    decision = evaluate_handoff_requirement(
        intent=_intent("support_emergency"), tool_signaled_handoff=True, tool_handoff_reason="unrelated reason"
    )
    assert decision.reason_code == "safety_incident"  # the mandatory reason, not the tool's


def test_tool_signaled_handoff_when_intent_is_not_mandatory():
    decision = evaluate_handoff_requirement(
        intent=_intent("general_amenities"), tool_signaled_handoff=True, tool_handoff_reason="Wants a manager"
    )
    assert decision.required is True
    assert decision.reason_code == "explicit_human_request"
    assert decision.summary == "Wants a manager"


def test_provider_failure_triggers_handoff():
    decision = evaluate_handoff_requirement(intent=_intent("general_amenities"), provider_failed=True)
    assert decision.required is True
    assert decision.reason_code == "provider_failure"


def test_repeated_tool_failures_trigger_handoff_at_threshold():
    below_threshold = evaluate_handoff_requirement(intent=_intent("general_amenities"), consecutive_tool_failures=1)
    at_threshold = evaluate_handoff_requirement(intent=_intent("general_amenities"), consecutive_tool_failures=2)
    assert below_threshold.required is False
    assert at_threshold.required is True
    assert at_threshold.reason_code == "repeated_tool_failure"


def test_repeated_low_confidence_triggers_handoff_at_threshold():
    below_threshold = evaluate_handoff_requirement(
        intent=_intent("unknown"), consecutive_low_confidence_count=2
    )
    at_threshold = evaluate_handoff_requirement(intent=_intent("unknown"), consecutive_low_confidence_count=3)
    assert below_threshold.required is False
    assert at_threshold.required is True
    assert at_threshold.reason_code == "repeated_low_confidence"


def test_no_signals_at_all_means_no_handoff():
    decision = evaluate_handoff_requirement(intent=_intent("general_amenities"))
    assert decision.required is False
    assert decision.reason_code is None


# --- staff summary --------------------------------------------------------------


def test_summarize_conversation_for_staff_includes_key_facts():
    intent = _intent("support_emergency")
    decision = evaluate_handoff_requirement(intent=intent)
    summary = summarize_conversation_for_staff(
        guest_message="Someone is having a medical emergency",
        intent=intent,
        entities={"guest_name": "Jane Guest"},
        handoff=decision,
    )
    assert "safety_incident" in summary
    assert "Jane Guest" in summary
    assert "support_emergency" in summary


def test_summarize_conversation_for_staff_handles_no_entities():
    intent = _intent("support_human_agent_request")
    decision = evaluate_handoff_requirement(intent=intent)
    summary = summarize_conversation_for_staff(
        guest_message="Can I speak to someone?", intent=intent, entities={}, handoff=decision
    )
    assert "none captured" in summary
