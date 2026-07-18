"""Pure-logic tests for the flow-state validation layer — no network
access, no database. Regression tests are pinned for two real bugs found
by smoke-testing against realistic conversation scenarios before writing
these: (1) a guest's very first message being an already-specific request
couldn't reach its target state because `greeting` only allowed
`discovering_needs`; (2) confirmed the reverse case (an unrelated jump
attempt from a terminal-ish state) correctly stays put rather than
silently forcing an invalid transition.
"""

from app.orchestration.constants import ALL_FLOW_STATES, FLOW_STATES_BY_DIALOGUE_STATE
from app.orchestration.domain import DetectedIntent, ExtractedEntities
from app.orchestration.flow.engine import apply_handoff, determine_missing_information, next_state, resume_after_handoff
from app.orchestration.flow.states import ALLOWED_DIALOGUE_TRANSITIONS, is_valid_flow_state, is_valid_transition


def test_every_dialogue_state_has_a_transition_entry():
    assert set(ALLOWED_DIALOGUE_TRANSITIONS) == set(FLOW_STATES_BY_DIALOGUE_STATE)


def test_every_flow_state_is_registered():
    for state in ALL_FLOW_STATES:
        assert isinstance(state, str) and state


def test_escalation_and_closed_reachable_from_every_state():
    for from_state, targets in ALLOWED_DIALOGUE_TRANSITIONS.items():
        if from_state in ("confirmation", "upselling", "escalation", "closed"):
            continue  # these have their own narrower, deliberate exit sets
        assert "escalation" in targets
        assert "closed" in targets


def test_is_valid_flow_state_rejects_flow_state_from_wrong_dialogue_state():
    assert is_valid_flow_state("booking", "collecting_stay_details") is False
    assert is_valid_flow_state("collecting_information", "collecting_stay_details") is True


def test_is_valid_transition_same_state_is_always_valid():
    assert is_valid_transition("booking", "booking") is True


def test_is_valid_transition_rejects_unreachable_jump():
    assert is_valid_transition("confirmation", "collecting_information") is False


def test_is_valid_transition_allows_registered_edge():
    assert is_valid_transition("collecting_information", "booking") is True


# --- regression: greeting must reach specific request targets directly ------


def test_first_message_already_a_specific_booking_request_reaches_target_directly():
    intent = DetectedIntent(primary_intent="room_booking_request", confidence=0.9)
    dialogue_state, flow_state = next_state(
        current_dialogue_state="greeting", current_flow_state="new_conversation", intent=intent
    )
    assert dialogue_state == "collecting_information"
    assert flow_state == "collecting_stay_details"


def test_first_message_dining_reservation_reaches_target_directly():
    intent = DetectedIntent(primary_intent="dining_reservation_request", confidence=0.9)
    dialogue_state, flow_state = next_state(
        current_dialogue_state="greeting", current_flow_state="new_conversation", intent=intent
    )
    assert dialogue_state == "collecting_information"


def test_first_message_complaint_reaches_support_directly():
    intent = DetectedIntent(primary_intent="support_complaint", confidence=0.8)
    dialogue_state, flow_state = next_state(
        current_dialogue_state="greeting", current_flow_state="new_conversation", intent=intent
    )
    assert dialogue_state == "support"
    assert flow_state == "complaint_handling"


def test_ambiguous_first_message_moves_to_discovering_needs():
    intent = DetectedIntent(primary_intent="unknown", confidence=0.0)
    dialogue_state, flow_state = next_state(
        current_dialogue_state="greeting", current_flow_state="new_conversation", intent=intent
    )
    assert dialogue_state == "discovering_needs"


# --- mandatory handoff always wins, regardless of current state ------------


def test_mandatory_handoff_overrides_any_in_progress_flow():
    intent = DetectedIntent(primary_intent="support_emergency", confidence=1.0)
    dialogue_state, flow_state = next_state(
        current_dialogue_state="collecting_information",
        current_flow_state="collecting_stay_details",
        intent=intent,
        mandatory_handoff=True,
    )
    assert dialogue_state == "escalation"
    assert flow_state == "human_handoff_requested"


def test_invalid_transition_target_leaves_conversation_in_place():
    # confirmation cannot jump straight back into collecting_information
    # per the transition graph — a genuinely new, unrelated request while
    # awaiting staff confirmation should not silently force state.
    intent = DetectedIntent(primary_intent="room_booking_request", confidence=0.9)
    dialogue_state, flow_state = next_state(
        current_dialogue_state="confirmation", current_flow_state="awaiting_staff_confirmation", intent=intent
    )
    assert dialogue_state == "confirmation"
    assert flow_state == "awaiting_staff_confirmation"


# --- handoff / resume ---------------------------------------------------------


def test_apply_handoff_requested_vs_active():
    requested = apply_handoff(active=False)
    active = apply_handoff(active=True)
    assert requested == ("escalation", "human_handoff_requested")
    assert active == ("escalation", "human_handoff_active")


def test_resume_after_handoff_from_escalation_restarts_discovery():
    dialogue_state, flow_state = resume_after_handoff("escalation", "human_handoff_active")
    assert dialogue_state == "discovering_needs"
    assert flow_state == "general_enquiry"


def test_resume_after_handoff_from_mid_flow_returns_to_same_place():
    dialogue_state, flow_state = resume_after_handoff("collecting_information", "collecting_stay_details")
    assert dialogue_state == "collecting_information"
    assert flow_state == "collecting_stay_details"


# --- missing information ------------------------------------------------------


def test_missing_information_detects_gaps():
    entities = ExtractedEntities(values={"check_in_date": "15 July 2026"})
    result = determine_missing_information("collecting_stay_details", entities)
    assert "num_nights" in result.required_fields
    assert "adults" in result.required_fields
    assert result.has_gaps is True
    assert result.prompt is not None


def test_missing_information_empty_when_all_fields_present():
    entities = ExtractedEntities(values={"check_in_date": "15 July 2026", "num_nights": 3, "adults": 2})
    result = determine_missing_information("collecting_stay_details", entities)
    assert result.has_gaps is False
    assert result.prompt is None


def test_missing_information_for_unregistered_flow_state_is_empty():
    result = determine_missing_information("comparing_rooms", ExtractedEntities())
    assert result.has_gaps is False
