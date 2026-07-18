"""Pure-logic tests for the context-assembler's trimming/truncation logic
— no database, no network. Uses the boundary-case fixtures the Phase 4
brief explicitly calls for (empty/low-confidence/excessive/conflicting/
safety-critical retrieval). The full assemble_context() integration path
(real DB + retrieval call) is covered separately in
test_orchestration_pipeline_integration.py once the pipeline exists,
matching Phase 3's pattern of pure-logic-first, DB-integration-second.
"""

from app.customers.models import Customer
from app.orchestration.context import fixtures
from app.orchestration.context.assembler import (
    ConversationTurn,
    _sanitize_guest_profile,
    _trim_citations_to_budget,
    _trim_turns_to_budget,
)


def test_empty_retrieval_produces_no_citations_and_no_truncation():
    kept, truncated = _trim_citations_to_budget(fixtures.empty_retrieval(), max_tokens=500)
    assert kept == []
    assert truncated is False


def test_low_confidence_retrieval_is_kept_when_it_fits_budget():
    citations = fixtures.low_confidence_retrieval()
    kept, truncated = _trim_citations_to_budget(citations, max_tokens=500)
    assert len(kept) == 1
    assert truncated is False


def test_excessive_retrieval_is_truncated_under_tight_budget():
    citations = fixtures.excessive_retrieval(50)
    kept, truncated = _trim_citations_to_budget(citations, max_tokens=200)
    assert len(kept) < len(citations)
    assert truncated is True


def test_excessive_retrieval_all_kept_under_generous_budget():
    citations = fixtures.excessive_retrieval(3)
    kept, truncated = _trim_citations_to_budget(citations, max_tokens=100_000)
    assert len(kept) == 3
    assert truncated is False


def test_conflicting_sources_preserve_authoritative_first():
    citations = fixtures.conflicting_sources()
    kept, _ = _trim_citations_to_budget(citations, max_tokens=1000)
    assert kept[0].source_priority == "critical"
    assert kept[0].authoritative is True


def test_safety_critical_content_never_dropped_even_under_absurd_budget():
    citations = fixtures.safety_critical_retrieval()
    kept, truncated = _trim_citations_to_budget(citations, max_tokens=1)
    assert len(kept) == 1
    assert kept[0].source_priority == "critical"


def test_critical_citation_survives_alongside_lower_priority_ones_under_pressure():
    citations = fixtures.conflicting_sources()  # one critical, one normal
    # Budget only large enough for roughly one citation's worth of tokens.
    kept, truncated = _trim_citations_to_budget(citations, max_tokens=20)
    assert any(c.source_priority == "critical" for c in kept)


# --- conversation turns -------------------------------------------------------


def test_turns_recency_weighting_drops_oldest_first():
    turns = [
        ConversationTurn(role="customer", content="old message " * 50),
        ConversationTurn(role="ai", content="middle message " * 50),
        ConversationTurn(role="customer", content="most recent message"),
    ]
    kept, truncated = _trim_turns_to_budget(turns, max_tokens=15)
    assert truncated is True
    assert kept[-1].content == "most recent message"
    assert turns[0] not in kept


def test_all_turns_kept_under_generous_budget():
    turns = [ConversationTurn(role="customer", content="hi"), ConversationTurn(role="ai", content="hello")]
    kept, truncated = _trim_turns_to_budget(turns, max_tokens=10_000)
    assert len(kept) == 2
    assert truncated is False


def test_empty_turns_list():
    kept, truncated = _trim_turns_to_budget([], max_tokens=100)
    assert kept == []
    assert truncated is False


# --- guest profile sanitization -----------------------------------------------


def test_sanitize_guest_profile_excludes_internal_fields():
    customer = Customer(
        full_name="Jane Guest",
        preferred_language="en",
        loyalty_reference="GOLD-123",
        resort_preferences={"favourite_room": "Garden Deluxe"},
    )
    profile = _sanitize_guest_profile(customer)
    assert profile["full_name"] == "Jane Guest"
    assert profile["loyalty_reference"] == "GOLD-123"
    assert "confirmed_preferences" in profile
    assert "id" not in profile
    assert "lifetime_value" not in profile


def test_sanitize_guest_profile_separates_ai_inferred_from_confirmed():
    """rules.md §6: an AI inference must never be presented to the model as
    if it were a staff-verified fact — the two live in different profile
    keys, not merged into one blob."""
    customer = Customer(
        full_name="Jane Guest",
        preferred_language="en",
        resort_preferences={
            "favourite_room": "Garden Deluxe",
            "ai_inferred": {"dietary_restrictions": {"value": "vegan", "confidence": 0.8}},
        },
    )
    profile = _sanitize_guest_profile(customer)
    assert profile["confirmed_preferences"] == {"favourite_room": "Garden Deluxe"}
    assert profile["ai_noted_preferences_unconfirmed"] == {"dietary_restrictions": "vegan"}


def test_sanitize_guest_profile_handles_none_customer():
    assert _sanitize_guest_profile(None) == {}


def test_sanitize_guest_profile_omits_empty_fields():
    customer = Customer(full_name=None, preferred_language="en", loyalty_reference=None, resort_preferences={})
    profile = _sanitize_guest_profile(customer)
    assert "full_name" not in profile
    assert "loyalty_reference" not in profile
    assert "resort_preferences" not in profile
