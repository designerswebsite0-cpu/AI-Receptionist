"""Pure-logic tests for the tool registry and validation layer — no
network, no database. DB-backed handler execution is covered separately
in test_orchestration_tool_handlers.py.
"""

import pytest

from app.orchestration.llm.base import LLMToolCall
from app.orchestration.tools.registry import ToolDefinition, get_tool, list_tools, to_openai_tools
from app.orchestration.tools.validation import validate_tool_call


def test_no_tool_ever_claims_booking_payment_or_refund_completion():
    forbidden_terms = ("confirm_booking", "process_payment", "issue_refund", "cancel_booking")
    tool_names = {tool.name for tool in list_tools()}
    assert not tool_names.intersection(forbidden_terms)


def test_every_registered_tool_uses_a_valid_permission_level():
    for tool in list_tools():
        assert tool.permission_level in ("guest_safe", "requires_guest_confirmation", "requires_staff_approval")


def test_get_tool_returns_none_for_unknown_name():
    assert get_tool("does_not_exist") is None


def test_to_openai_tools_shape():
    rendered = to_openai_tools()
    assert all(entry["type"] == "function" for entry in rendered)
    assert all("name" in entry["function"] for entry in rendered)


def test_invalid_permission_level_rejected_at_construction():
    with pytest.raises(ValueError):
        ToolDefinition(
            name="bad_tool",
            description="x",
            input_schema={},
            required_fields=(),
            permission_level="not_a_real_level",
        )


# --- validation ----------------------------------------------------------------


def test_validate_unknown_tool_is_denied():
    call = LLMToolCall(call_id="call_1", tool_name="totally_made_up_tool", arguments={})
    decision = validate_tool_call(call)
    assert decision.decision == "denied"
    assert "Unknown tool" in decision.denial_reason


def test_validate_missing_required_field_is_denied():
    call = LLMToolCall(call_id="call_1", tool_name="create_room_booking", arguments={"check_in_date": "2026-08-01"})
    decision = validate_tool_call(call)
    assert decision.decision == "denied"
    assert "guest_phone" in decision.denial_reason


def test_validate_complete_call_is_approved_for_execution():
    call = LLMToolCall(
        call_id="call_1",
        tool_name="create_room_booking",
        arguments={
            "check_in_date": "2026-08-01",
            "check_out_date": "2026-08-03",
            "num_guests": 2,
            "room_type": "Garden Deluxe Room",
            "guest_name": "Jane Guest",
            "guest_phone": "+14155550100",
        },
    )
    decision = validate_tool_call(call)
    assert decision.decision == "execute"


def test_validate_read_only_tool_with_no_required_fields():
    call = LLMToolCall(call_id="call_1", tool_name="read_guest_profile", arguments={})
    decision = validate_tool_call(call)
    assert decision.decision == "execute"


def test_validate_request_human_assistance_requires_reason():
    call = LLMToolCall(call_id="call_1", tool_name="request_human_assistance", arguments={})
    decision = validate_tool_call(call)
    assert decision.decision == "denied"

    call_with_reason = LLMToolCall(
        call_id="call_1", tool_name="request_human_assistance", arguments={"reason": "Payment dispute"}
    )
    decision_with_reason = validate_tool_call(call_with_reason)
    assert decision_with_reason.decision == "execute"
