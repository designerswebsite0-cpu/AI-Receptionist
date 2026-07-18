"""Entity extraction — functions.md §28's extract_guest_entities.
Deterministic regex/rule-based parsing for dates, numbers, and contact
details (unambiguous, no need for a model call); LLM-assisted extraction
only for genuinely semantic fields (room_category, dietary_restrictions,
occasion, urgency, etc.) when a provider is supplied.
"""

import json
import re

from app.orchestration.domain import ExtractedEntities
from app.orchestration.llm.base import LLMMessage, LLMProvider, LLMProviderError

_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_PATTERN = re.compile(r"(?:\+\d{1,3}[\s-]?)?\d{10}\b|\+\d{1,3}[\s-]?\d{3,4}[\s-]?\d{3,4}[\s-]?\d{3,4}")
_BOOKING_REFERENCE_PATTERN = re.compile(r"\b[A-Z]{2,4}-?\d{4,8}\b")

# "15 July 2026", "July 15, 2026", "15/07/2026", "15-07-2026" — deliberately
# not a general natural-language date parser (no dateutil dependency in
# this codebase); relative phrases ("next weekend") are left for the LLM
# path, which is exactly the kind of semantic interpretation Step 3 of the
# brief says should NOT be handled deterministically.
_MONTH_NAMES = (
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
)
_DATE_TEXT_PATTERN = re.compile(
    r"\b(\d{1,2})\s+(" + "|".join(_MONTH_NAMES) + r")\s*,?\s*(\d{4})?\b", re.IGNORECASE
)
_DATE_NUMERIC_PATTERN = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b")

_ADULTS_PATTERN = re.compile(r"(\d+)\s*adults?")
_CHILDREN_PATTERN = re.compile(r"(\d+)\s*(?:children|child|kids?)")
_NIGHTS_PATTERN = re.compile(r"(\d+)\s*nights?")
_ROOMS_PATTERN = re.compile(r"(\d+)\s*rooms?")
_BUDGET_PATTERN = re.compile(
    r"(?:inr|rs\.?|₹|\$|usd)\s*([\d,]+)|([\d,]+)\s*(?:inr|rupees|rs\.?|dollars)", re.IGNORECASE
)


def _extract_dates(text: str) -> list[str]:
    dates = []
    for match in _DATE_TEXT_PATTERN.finditer(text):
        day, month, year = match.groups()
        dates.append(f"{day} {month.title()} {year or ''}".strip())
    for match in _DATE_NUMERIC_PATTERN.finditer(text):
        dates.append(match.group(0))
    return dates


def extract_entities_deterministic(text: str) -> ExtractedEntities:
    values: dict[str, object] = {}
    confidence: dict[str, float] = {}
    source: dict[str, str] = {}

    def _set(field_name: str, value) -> None:
        values[field_name] = value
        confidence[field_name] = 1.0
        source[field_name] = "deterministic"

    emails = _EMAIL_PATTERN.findall(text)
    if emails:
        _set("email", emails[0])

    phones = _PHONE_PATTERN.findall(text)
    if phones:
        _set("phone", phones[0].strip())

    dates = _extract_dates(text)
    if dates:
        _set("check_in_date", dates[0])
        if len(dates) > 1:
            _set("check_out_date", dates[1])

    adults_match = _ADULTS_PATTERN.search(text)
    if adults_match:
        _set("adults", int(adults_match.group(1)))

    children_match = _CHILDREN_PATTERN.search(text)
    if children_match:
        _set("children", int(children_match.group(1)))

    nights_match = _NIGHTS_PATTERN.search(text)
    if nights_match:
        _set("num_nights", int(nights_match.group(1)))

    rooms_match = _ROOMS_PATTERN.search(text)
    if rooms_match:
        _set("num_rooms", int(rooms_match.group(1)))

    budget_match = _BUDGET_PATTERN.search(text)
    if budget_match:
        raw = (budget_match.group(1) or budget_match.group(2) or "").replace(",", "")
        if raw.isdigit():
            _set("budget", int(raw))

    booking_ref_match = _BOOKING_REFERENCE_PATTERN.search(text)
    if booking_ref_match:
        _set("booking_reference", booking_ref_match.group(0))

    return ExtractedEntities(values=values, confidence=confidence, source=source)


_LLM_SEMANTIC_FIELDS = (
    "room_category", "view_preference", "meal_plan", "dietary_restrictions", "allergies",
    "occasion", "accessibility_needs", "activity", "spa_service", "transfer_origin",
    "transfer_destination", "guest_name", "language", "urgency",
)


async def extract_entities(text: str, *, llm_provider: LLMProvider | None = None) -> ExtractedEntities:
    """The single entry point orchestration code calls. Deterministic
    fields are always extracted; semantic fields are only ever filled in
    when a provider is supplied, and are clearly marked source='llm' with
    a sub-1.0 confidence — never conflated with a verified deterministic
    match."""
    result = extract_entities_deterministic(text)

    if llm_provider is None:
        return result

    try:
        llm_values = await _extract_semantic_entities(text, llm_provider)
    except LLMProviderError:
        return result

    for field_name, value in llm_values.items():
        if field_name in _LLM_SEMANTIC_FIELDS and value not in (None, ""):
            result.values[field_name] = value
            result.confidence[field_name] = 0.7
            result.source[field_name] = "llm"

    return result


async def _extract_semantic_entities(text: str, llm_provider: LLMProvider) -> dict:
    prompt = (
        "Extract these fields from the guest message if present, as JSON "
        f"with exactly these keys (use null if absent): {list(_LLM_SEMANTIC_FIELDS)}.\n"
        f"Guest message: {text}"
    )
    result = await llm_provider.complete(
        [
            LLMMessage(role="system", content="You extract structured fields. Only output the requested JSON."),
            LLMMessage(role="user", content=prompt),
        ],
        response_format={"type": "json_object"},
    )
    try:
        parsed = json.loads(result.text)
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}
