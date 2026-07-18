"""Deterministic validation of an LLM-proposed tool call — the backend
decides, the LLM only requests (docs/CLAUDE.md "Tool Design"). Every
proposed call is checked against the registry before anything executes;
an unknown tool name, a missing required field, or a permission level
requiring guest/staff sign-off are all caught here, never left to the
model's own judgment.
"""

from app.orchestration.domain import ToolDecision
from app.orchestration.llm.base import LLMToolCall
from app.orchestration.tools.registry import get_tool


def validate_tool_call(call: LLMToolCall) -> ToolDecision:
    tool = get_tool(call.tool_name)
    if tool is None:
        return ToolDecision(
            tool_name=call.tool_name,
            tool_input=call.arguments,
            decision="denied",
            denial_reason=f"Unknown tool '{call.tool_name}'",
        )

    missing = [field for field in tool.required_fields if not call.arguments.get(field)]
    if missing:
        return ToolDecision(
            tool_name=call.tool_name,
            tool_input=call.arguments,
            decision="denied",
            denial_reason=f"Missing required field(s): {', '.join(missing)}",
        )

    if tool.permission_level == "requires_staff_approval":
        return ToolDecision(tool_name=call.tool_name, tool_input=call.arguments, decision="needs_staff_approval")
    if tool.permission_level == "requires_guest_confirmation":
        return ToolDecision(tool_name=call.tool_name, tool_input=call.arguments, decision="needs_guest_confirmation")
    return ToolDecision(tool_name=call.tool_name, tool_input=call.arguments, decision="execute")
