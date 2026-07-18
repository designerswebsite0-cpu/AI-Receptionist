"""Static flow-state data: which DIALOGUE_STATE transitions are allowed,
which intents suggest which starting state, and which entities are
required before a flow_state is considered "ready to proceed."

None of this touches conversations.current_state's actual CHECK
constraint or storage — app.conversations.state_machine.transition_state
remains the permissive, durable write path (its own docstring hands this
validation responsibility to Phase 4). This module is purely the
validation logic layered on top.
"""

from app.orchestration.constants import ALL_FLOW_STATES, FLOW_STATES_BY_DIALOGUE_STATE

# escalation/closed are reachable from every state — safety valve
# (mandatory handoff can fire from anywhere) and terminal state.
_UNIVERSAL_TARGETS = ("escalation", "closed")

_DISCOVERING_NEEDS_TARGETS = {"collecting_information", "recommending", "support", "upselling", *_UNIVERSAL_TARGETS}

ALLOWED_DIALOGUE_TRANSITIONS: dict[str, set[str]] = {
    # `greeting` is "discovering_needs before any message has been
    # classified" — it must reach everywhere discovering_needs reaches,
    # not just discovering_needs itself. Real bug caught by smoke-testing
    # against an actual guest message: a first message that's already a
    # specific, unambiguous request ("book a villa for 2 adults, 15 July"
    # — extremely common in practice, not an edge case) needs to jump
    # straight to collecting_information/recommending/etc., not be forced
    # through an artificial two-hop discovering_needs detour.
    "greeting": {"discovering_needs", *_DISCOVERING_NEEDS_TARGETS},
    "discovering_needs": _DISCOVERING_NEEDS_TARGETS,
    "collecting_information": {"recommending", "booking", "waiting", "support", *_UNIVERSAL_TARGETS},
    "recommending": {"booking", "collecting_information", "upselling", "support", *_UNIVERSAL_TARGETS},
    "booking": {"waiting", "confirmation", "collecting_information", "support", *_UNIVERSAL_TARGETS},
    "waiting": {"confirmation", "booking", "support", *_UNIVERSAL_TARGETS},
    "confirmation": {"upselling", "closed", "support", "escalation"},
    "upselling": {"closed", "booking", "support", "escalation"},
    "support": {"discovering_needs", *_UNIVERSAL_TARGETS},
    "escalation": {"support", "closed"},
    "closed": {"discovering_needs"},  # a resolved conversation can be reopened (same row), never auto-reopens itself
}

# Which (current_state, flow_state) a detected intent should move the
# conversation toward, if the conversation is still in `greeting` or
# `discovering_needs` (i.e. this is deciding WHERE to go, not overriding
# an already-in-progress flow — see flow.engine.next_state).
INTENT_TARGET_STATE: dict[str, tuple[str, str]] = {
    "room_booking_request": ("collecting_information", "collecting_stay_details"),
    "room_modification_request": ("booking", "modification_request"),
    "room_cancellation_request": ("booking", "cancellation_request"),
    "room_availability_enquiry": ("collecting_information", "collecting_stay_details"),
    "room_price_enquiry": ("recommending", "comparing_rooms"),
    "room_category_enquiry": ("recommending", "comparing_rooms"),
    "room_villa_enquiry": ("recommending", "comparing_rooms"),
    "dining_reservation_request": ("collecting_information", "restaurant_order_collection"),
    "dining_food_order_request": ("collecting_information", "restaurant_order_collection"),
    "transport_pickup_request": ("collecting_information", "transfer_detail_collection"),
    "transport_drop_request": ("collecting_information", "transfer_detail_collection"),
    "transport_airport_transfer": ("discovering_needs", "transfer_enquiry"),
    "activity_spa_enquiry": ("discovering_needs", "activity_enquiry"),
    "activity_general_enquiry": ("discovering_needs", "activity_enquiry"),
    "support_complaint": ("support", "complaint_handling"),
    "support_service_issue": ("support", "complaint_handling"),
    "support_emergency": ("escalation", "emergency_escalation"),
    "support_safety_concern": ("escalation", "emergency_escalation"),
    "support_medical_concern": ("escalation", "emergency_escalation"),
    "support_human_agent_request": ("escalation", "human_handoff_requested"),
}

# Entities required before a flow_state is considered ready to proceed to
# the next step — drives detect_missing_information / the follow-up
# question the orchestrator should ask instead of guessing.
REQUIRED_ENTITIES_BY_FLOW_STATE: dict[str, tuple[str, ...]] = {
    "collecting_stay_details": ("check_in_date", "num_nights", "adults"),
    "collecting_guest_details": ("guest_name",),
    "restaurant_order_collection": ("check_in_date",),  # which date/meal the order is for
    "transfer_detail_collection": ("transfer_origin", "transfer_destination", "arrival_details"),
    "booking_assistance": ("check_in_date", "num_nights", "adults", "room_category"),
}

MISSING_INFO_PROMPTS: dict[str, str] = {
    "check_in_date": "What date would you like to check in?",
    "num_nights": "How many nights will you be staying?",
    "adults": "How many adults will be staying?",
    "guest_name": "Could I have the name for the reservation?",
    "transfer_origin": "Where should we arrange pickup from?",
    "transfer_destination": "Where would you like to be dropped off?",
    "arrival_details": "Could you share your flight or arrival details?",
    "room_category": "Which room category would you prefer?",
}


def is_valid_transition(from_state: str, to_state: str) -> bool:
    if from_state == to_state:
        return True
    return to_state in ALLOWED_DIALOGUE_TRANSITIONS.get(from_state, set())


def is_valid_flow_state(dialogue_state: str, flow_state: str) -> bool:
    return flow_state in FLOW_STATES_BY_DIALOGUE_STATE.get(dialogue_state, ())


assert set(ALLOWED_DIALOGUE_TRANSITIONS) == set(FLOW_STATES_BY_DIALOGUE_STATE), (
    "Every canonical DIALOGUE_STATE must have an explicit transition entry"
)
assert all(state in ALL_FLOW_STATES for states in FLOW_STATES_BY_DIALOGUE_STATE.values() for state in states)
