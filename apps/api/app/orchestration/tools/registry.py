"""Typed tool registry. No tool here ever claims a booking/payment/refund
succeeded — create_*_enquiry tools only ever write a service_requests row
(app.orchestration.service.create_service_request), per
docs/phase-4/PHASE_4_IMPLEMENTATION_PLAN.md §2/§8's "safe enquiry record,
not a fake completed operation" rule. `search_resort_knowledge` is
registered here (so the LLM can request a follow-up lookup) but actually
executed in app.orchestration.pipeline, not app.orchestration.tools.
handlers — it needs the same embedding provider/reranker the pipeline
already holds, and threading those through the generic dispatch would
couple this module to Phase 3 providers unnecessarily.
"""

from dataclasses import dataclass

from app.orchestration.constants import TOOL_PERMISSION_LEVELS


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict
    required_fields: tuple[str, ...]
    permission_level: str
    idempotent: bool = True
    timeout_seconds: float = 10.0

    def __post_init__(self):
        if self.permission_level not in TOOL_PERMISSION_LEVELS:
            raise ValueError(f"permission_level must be one of {TOOL_PERMISSION_LEVELS}")


_REGISTRY: dict[str, ToolDefinition] = {}


def register_tool(definition: ToolDefinition) -> None:
    _REGISTRY[definition.name] = definition


def get_tool(name: str) -> ToolDefinition | None:
    return _REGISTRY.get(name)


def list_tools() -> list[ToolDefinition]:
    return list(_REGISTRY.values())


def to_openai_tools() -> list[dict]:
    """Renders the registry into OpenAI's function-calling `tools` shape."""
    return [
        {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.input_schema}}
        for t in _REGISTRY.values()
    ]


def _enquiry_schema(*extra_props: str) -> dict:
    props = {name: {"type": "string"} for name in extra_props}
    return {"type": "object", "properties": props}


register_tool(
    ToolDefinition(
        name="search_resort_knowledge",
        description=(
            "Search the resort's knowledge base for a specific follow-up question not "
            "already answered by the retrieved context you were given."
        ),
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        required_fields=("query",),
        permission_level="guest_safe",
    )
)
register_tool(
    ToolDefinition(
        name="read_guest_profile",
        description="Read the current guest's own profile facts (name, preferences, loyalty reference).",
        input_schema={"type": "object", "properties": {}},
        required_fields=(),
        permission_level="guest_safe",
    )
)
register_tool(
    ToolDefinition(
        name="update_guest_preferences",
        description="Update a preference the guest explicitly stated in this conversation.",
        input_schema={
            "type": "object",
            "properties": {"preferences": {"type": "object"}},
            "required": ["preferences"],
        },
        required_fields=("preferences",),
        permission_level="guest_safe",
    )
)
register_tool(
    ToolDefinition(
        name="create_booking_enquiry",
        description="Record a room booking enquiry for staff follow-up. Does NOT confirm a booking.",
        input_schema={
            "type": "object",
            "properties": {
                "check_in_date": {"type": "string"},
                "num_nights": {"type": "integer"},
                "adults": {"type": "integer"},
                "room_category": {"type": "string"},
            },
            "required": ["check_in_date"],
        },
        required_fields=("check_in_date",),
        permission_level="guest_safe",
    )
)
register_tool(
    ToolDefinition(
        name="create_dining_enquiry",
        description="Record a dining reservation or in-room dining enquiry for staff follow-up.",
        input_schema=_enquiry_schema("restaurant", "date", "time", "party_size", "dietary_restrictions"),
        required_fields=(),
        permission_level="guest_safe",
    )
)
register_tool(
    ToolDefinition(
        name="create_spa_enquiry",
        description="Record a spa treatment enquiry for staff follow-up.",
        input_schema=_enquiry_schema("service", "date", "time"),
        required_fields=(),
        permission_level="guest_safe",
    )
)
register_tool(
    ToolDefinition(
        name="create_activity_enquiry",
        description="Record an activity or experience enquiry for staff follow-up.",
        input_schema=_enquiry_schema("activity", "date", "party_size"),
        required_fields=(),
        permission_level="guest_safe",
    )
)
register_tool(
    ToolDefinition(
        name="create_transfer_enquiry",
        description="Record an airport/local transfer enquiry for staff follow-up.",
        input_schema=_enquiry_schema("transfer_origin", "transfer_destination", "arrival_details"),
        required_fields=(),
        permission_level="guest_safe",
    )
)
register_tool(
    ToolDefinition(
        name="record_complaint",
        description="Record a guest complaint for staff review.",
        input_schema={"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]},
        required_fields=("summary",),
        permission_level="guest_safe",
    )
)
register_tool(
    ToolDefinition(
        name="request_human_assistance",
        description="Escalate the conversation to a human staff member.",
        input_schema={"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]},
        required_fields=("reason",),
        permission_level="guest_safe",
    )
)
register_tool(
    ToolDefinition(
        name="retrieve_request_status",
        description="Check the status of a previously created service request in this conversation.",
        input_schema={"type": "object", "properties": {"request_id": {"type": "string"}}, "required": ["request_id"]},
        required_fields=("request_id",),
        permission_level="guest_safe",
        idempotent=True,
    )
)
