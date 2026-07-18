"""The validated transition layer app.conversations.state_machine's own
docstring hands to Phase 4. app.conversations.state_machine.transition_state
remains the actual durable write (permissive, audited); this module decides
*what* to transition to and *whether* that's allowed, then callers pass the
result to transition_state / conversations.service.change_dialogue_state.

functions.md §28: get_conversation_state / update_conversation_state /
detect_missing_information live here.
"""

from app.orchestration.domain import DetectedIntent, ExtractedEntities, MissingInformation
from app.orchestration.flow.states import (
    INTENT_TARGET_STATE,
    MISSING_INFO_PROMPTS,
    REQUIRED_ENTITIES_BY_FLOW_STATE,
    is_valid_transition,
)


def determine_missing_information(flow_state: str | None, entities: ExtractedEntities) -> MissingInformation:
    required = REQUIRED_ENTITIES_BY_FLOW_STATE.get(flow_state, ())
    missing = [field for field in required if entities.get(field) is None]
    prompt = MISSING_INFO_PROMPTS.get(missing[0]) if missing else None
    return MissingInformation(required_fields=missing, prompt=prompt)


def next_state(
    *,
    current_dialogue_state: str,
    current_flow_state: str | None,
    intent: DetectedIntent,
    mandatory_handoff: bool = False,
) -> tuple[str, str | None]:
    """Decides the next (dialogue_state, flow_state) pair. Never returns an
    invalid transition — if the intent's natural target isn't reachable
    from where the conversation currently is (e.g. a brand-new booking
    request arriving while already in `confirmation` for a different
    request), the conversation stays put rather than silently jumping;
    the caller (pipeline) is expected to ask a clarifying question or
    treat it as a new, parallel enquiry instead of forcing state.
    """
    if mandatory_handoff:
        return "escalation", "human_handoff_requested"

    target = INTENT_TARGET_STATE.get(intent.primary_intent)
    if target is None:
        if current_dialogue_state == "greeting":
            return "discovering_needs", "general_enquiry"
        return current_dialogue_state, current_flow_state

    target_dialogue_state, target_flow_state = target
    if is_valid_transition(current_dialogue_state, target_dialogue_state):
        return target_dialogue_state, target_flow_state
    return current_dialogue_state, current_flow_state


def apply_handoff(*, active: bool) -> tuple[str, str]:
    """`active=False` is the "handoff requested, awaiting staff pickup"
    moment; `active=True` is staff having actually taken over — kept as
    two distinct flow_states within the single `escalation` dialogue
    state so the dashboard can tell the difference."""
    return ("escalation", "human_handoff_active") if active else ("escalation", "human_handoff_requested")


def resume_after_handoff(previous_dialogue_state: str, previous_flow_state: str | None) -> tuple[str, str | None]:
    """AI re-entry after staff releases the conversation. Resumes exactly
    where it was — UNLESS that "where" was itself an escalation state,
    which would just loop the conversation straight back into handoff;
    in that case, restart from discovering_needs instead."""
    if previous_dialogue_state == "escalation":
        return "discovering_needs", "general_enquiry"
    return previous_dialogue_state, previous_flow_state
