"""Pure-logic tests for intent classification and entity extraction — no
network access, no database. LLM-assisted paths are tested separately
with MockLLMProvider (also no network call).
"""

from datetime import date

import pytest

from app.orchestration.constants import ALL_INTENTS
from app.orchestration.intent.classifier import classify_intent, classify_intent_deterministic, is_small_talk
from app.orchestration.intent.entities import extract_entities, extract_entities_deterministic, validate_stay_dates
from app.orchestration.llm.base import LLMProviderError, LLMResult
from app.orchestration.llm.mock_provider import MockLLMProvider

# --- deterministic classification --------------------------------------------


def test_detects_small_talk():
    assert is_small_talk("Hi there!") is True
    assert is_small_talk("Hello, I need help with a booking") is False


def test_classifies_checkin_question():
    result = classify_intent_deterministic("What time is check-in?")
    assert result.primary_intent == "general_checkin_checkout"
    assert result.confidence > 0


def test_classifies_emergency_as_primary_over_medical_secondary():
    result = classify_intent_deterministic("Someone is having a medical emergency, please help now")
    assert result.primary_intent == "support_emergency"
    assert "support_medical_concern" in result.all_intents


def test_unknown_intent_for_text_with_no_domain_keywords():
    result = classify_intent_deterministic("My email is guest@example.com and phone is 9876543210")
    assert result.primary_intent == "unknown"
    assert result.confidence == 0.0


def test_multi_intent_message_returns_secondary_intents():
    result = classify_intent_deterministic("I want to book a private pool villa for our honeymoon")
    assert result.primary_intent in result.all_intents
    assert len(result.all_intents) >= 1


@pytest.mark.parametrize("intent", ALL_INTENTS)
def test_every_taxonomy_intent_is_a_string(intent):
    assert isinstance(intent, str) and intent


# --- LLM-assisted escalation --------------------------------------------------


@pytest.mark.asyncio
async def test_classify_intent_skips_llm_when_deterministic_confidence_is_high():
    provider = MockLLMProvider()
    result = await classify_intent("Someone is having a medical emergency", llm_provider=provider)
    assert result.primary_intent == "support_emergency"
    assert provider.call_count == 0  # never escalated — deterministic was confident enough


@pytest.mark.asyncio
async def test_classify_intent_escalates_to_llm_when_deterministic_confidence_is_low():
    def responder(messages):
        return LLMResult(
            text='{"intent": "room_booking_request", "confidence": 0.9}',
            provider="mock", model="mock-llm", latency_ms=0,
        )

    provider = MockLLMProvider(responder=responder)
    result = await classify_intent("asdkj sending random text with no keywords", llm_provider=provider)

    assert provider.call_count == 1
    assert result.primary_intent == "room_booking_request"
    assert result.confidence == 0.9


@pytest.mark.asyncio
async def test_classify_intent_falls_back_to_deterministic_on_llm_error():
    class _FailingProvider:
        async def complete(self, *args, **kwargs):
            raise LLMProviderError("simulated failure")

    result = await classify_intent("completely ambiguous filler text", llm_provider=_FailingProvider())
    assert result.primary_intent == "unknown"  # deterministic fallback, not a crash


@pytest.mark.asyncio
async def test_classify_intent_ignores_llm_response_outside_taxonomy():
    bad_response = LLMResult(
        text='{"intent": "made_up_intent", "confidence": 0.9}', provider="mock", model="m", latency_ms=0
    )
    provider = MockLLMProvider(responses=[bad_response])
    result = await classify_intent("asdkj sending random text with no keywords", llm_provider=provider)
    assert result.primary_intent == "unknown"  # rejected the out-of-taxonomy value, kept the deterministic fallback


# --- deterministic entity extraction -----------------------------------------


def test_extracts_email_and_phone():
    entities = extract_entities_deterministic("My email is guest@example.com and phone is 9876543210")
    assert entities.get("email") == "guest@example.com"
    assert entities.get("phone") == "9876543210"
    assert entities.confidence["email"] == 1.0


def test_extracts_dates_adults_and_nights():
    entities = extract_entities_deterministic(
        "I want to book a room for 2 adults and 1 child from 15 July 2026 for 3 nights"
    )
    assert entities.get("check_in_date") == "15 July 2026"
    assert entities.get("adults") == 2
    assert entities.get("children") == 1
    assert entities.get("num_nights") == 3


def test_extracts_booking_reference():
    entities = extract_entities_deterministic("My booking reference is BK-12345")
    assert entities.get("booking_reference") == "BK-12345"


def test_no_entities_extracted_from_text_without_any():
    entities = extract_entities_deterministic("What time does the pool close?")
    assert entities.values == {}


# --- LLM-assisted entity extraction -------------------------------------------


@pytest.mark.asyncio
async def test_extract_entities_adds_semantic_fields_from_llm():
    provider = MockLLMProvider(
        responses=[
            LLMResult(
                text='{"room_category": "deluxe suite", "occasion": "honeymoon", "urgency": "low"}',
                provider="mock", model="m", latency_ms=0,
            )
        ]
    )
    entities = await extract_entities("We need a nice room for our honeymoon", llm_provider=provider)

    assert entities.get("room_category") == "deluxe suite"
    assert entities.get("occasion") == "honeymoon"
    assert entities.source["occasion"] == "llm"
    assert entities.confidence["occasion"] < 1.0


@pytest.mark.asyncio
async def test_extract_entities_without_provider_only_returns_deterministic():
    entities = await extract_entities("My email is guest@example.com", llm_provider=None)
    assert entities.get("email") == "guest@example.com"
    assert "occasion" not in entities.values


# --- stay date validation -------------------------------------------------------


_TODAY = date(2026, 7, 19)


def test_validate_stay_dates_accepts_a_normal_future_stay():
    issues = validate_stay_dates(
        {"check_in_date": "15 August 2026", "check_out_date": "20 August 2026"}, today=_TODAY
    )
    assert issues == []


def test_validate_stay_dates_flags_checkout_before_checkin():
    issues = validate_stay_dates(
        {"check_in_date": "21 August 2026", "check_out_date": "20 August 2026"}, today=_TODAY
    )
    assert any("not after the check-in date" in issue for issue in issues)


def test_validate_stay_dates_flags_checkout_equal_to_checkin():
    issues = validate_stay_dates(
        {"check_in_date": "20 August 2026", "check_out_date": "20 August 2026"}, today=_TODAY
    )
    assert any("not after the check-in date" in issue for issue in issues)


def test_validate_stay_dates_flags_a_check_in_already_in_the_past():
    issues = validate_stay_dates({"check_in_date": "1 January 2026"}, today=_TODAY)
    assert any("already passed" in issue for issue in issues)


def test_validate_stay_dates_flags_a_date_beyond_the_rate_card_validity_window():
    issues = validate_stay_dates({"check_in_date": "15 August 2027"}, today=_TODAY)
    assert any("validity window" in issue for issue in issues)


def test_validate_stay_dates_resolves_a_missing_year_to_the_next_upcoming_occurrence():
    # "1 October" with no year, asked on 19 July 2026, means this coming October — still
    # this year and well within the rate card's validity window, so no issues.
    issues = validate_stay_dates({"check_in_date": "1 October"}, today=_TODAY)
    assert issues == []


def test_validate_stay_dates_handles_numeric_format():
    issues = validate_stay_dates(
        {"check_in_date": "21/08/2026", "check_out_date": "20/08/2026"}, today=_TODAY
    )
    assert any("not after the check-in date" in issue for issue in issues)
