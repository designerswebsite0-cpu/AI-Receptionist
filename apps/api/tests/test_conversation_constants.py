from app.conversations.constants import CHANNELS, DIALOGUE_STATES, PRIORITIES, STATUSES


def test_statuses_include_all_phase2_brief_statuses_plus_retained_blocked():
    phase2_brief_statuses = {
        "open", "waiting_for_guest", "waiting_for_staff", "ai_handling",
        "human_handling", "escalated", "closed",
    }
    assert phase2_brief_statuses.issubset(set(STATUSES))
    assert "blocked" in STATUSES  # retained from architecture.md's original safety invariant


def test_dialogue_states_are_channel_neutral_and_match_functions_md():
    assert set(DIALOGUE_STATES) == {
        "greeting", "discovering_needs", "collecting_information", "recommending",
        "booking", "waiting", "confirmation", "upselling", "support", "escalation", "closed",
    }


def test_channels_are_current_phase_only():
    assert set(CHANNELS) == {"whatsapp", "webchat", "voice"}


def test_priorities_are_ordered_low_to_urgent():
    assert PRIORITIES == ("low", "normal", "high", "urgent")
