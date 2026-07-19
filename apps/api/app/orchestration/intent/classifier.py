"""Intent classification — functions.md §28's detect_guest_intent /
classify_multi_intent / resolve_follow_up_intent / detect_small_talk /
detect_sales_opportunity, implemented as one module.

Two-tier design: a deterministic keyword scorer runs first and is often
enough on its own (fast, free, no network call, fully testable without a
provider). When its confidence is below `_LLM_ESCALATION_THRESHOLD` and an
LLMProvider is supplied, the result is refined by asking the model to pick
from the same closed intent list — the LLM never invents a new intent
name, it only disambiguates among ALL_INTENTS. This mirrors
app.knowledge.retrieval's dense+sparse hybrid: cheap deterministic signal
first, model-assisted refinement only when genuinely needed.
"""

import json
import re

from app.orchestration.constants import ALL_INTENTS
from app.orchestration.domain import DetectedIntent
from app.orchestration.llm.base import LLMMessage, LLMProvider, LLMProviderError

_WORD_PATTERN = re.compile(r"[a-z0-9']+")

_LLM_ESCALATION_THRESHOLD = 0.45
_SECONDARY_INTENT_THRESHOLD = 0.30

_SMALL_TALK_PHRASES = (
    "hello", "hi there", "hey", "good morning", "good evening", "good afternoon",
    "how are you", "thank you", "thanks", "bye", "goodbye", "nice to meet you",
)

# Keyword sets per intent — built from the resort domain vocabulary in the
# Phase 4 brief and docs/functions.md/docs/Goal.md, not exhaustive NLP, but
# a real, testable first line of classification.
_INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    # General
    "general_resort_overview": ("about the resort", "tell me about", "resort overview", "what is rkpr"),
    "general_location_directions": ("location", "directions", "how to reach", "where is the resort", "address"),
    "general_contact_info": ("contact number", "phone number", "email address", "how to contact"),
    "general_checkin_checkout": ("check-in", "check in", "checkout", "check out", "arrival time", "departure time"),
    "general_amenities": ("amenities", "facilities", "what does the resort offer"),
    "general_accessibility": ("wheelchair", "accessible", "accessibility", "disability", "mobility"),
    "general_wifi": ("wifi", "wi-fi", "internet access", "internet connection"),
    "general_weather": ("weather", "climate", "what to pack", "temperature"),
    "general_policy": ("policy", "policies", "rules", "guest policy"),
    # Rooms
    "room_category_enquiry": ("room type", "room category", "kind of rooms", "categories of rooms"),
    "room_villa_enquiry": ("villa", "pool villa", "private villa"),
    "room_occupancy_enquiry": ("how many guests", "occupancy", "max occupancy", "sleeps how many"),
    "room_bed_configuration": ("bed configuration", "twin beds", "king bed", "double bed", "bed type"),
    "room_view_preference": ("view", "ocean view", "garden view", "valley view", "mountain view"),
    "room_private_pool_enquiry": ("private pool", "plunge pool", "own pool", "pool villa"),
    "room_accessibility_requirements": ("accessible room", "wheelchair accessible room", "roll-in shower"),
    "room_extra_bed_request": ("extra bed", "additional bed", "rollaway", "cot"),
    "room_connecting_request": ("connecting room", "adjoining room", "rooms next to each other"),
    "room_availability_enquiry": ("availability", "is there a room", "any rooms available", "vacancy"),
    "room_price_enquiry": ("room price", "room rate", "how much is a room", "cost of a room", "tariff"),
    "room_offer_enquiry": ("offer", "package", "discount", "deal", "promotion"),
    "room_booking_request": ("book a room", "make a reservation", "i want to book", "reserve a room"),
    "room_modification_request": ("change my booking", "modify reservation", "amend booking", "reschedule"),
    "room_cancellation_request": ("cancel my booking", "cancel reservation", "cancellation"),
    # Dining
    "dining_restaurant_info": ("restaurant", "dining venue", "which restaurants"),
    "dining_menu_enquiry": ("menu", "what food do you serve", "dishes available"),
    "dining_dietary_requirement": ("vegetarian", "vegan", "jain food", "dietary requirement", "gluten free"),
    "dining_allergen_enquiry": ("allergy", "allergen", "nut allergy", "food allergy"),
    "dining_in_room_dining": ("in-room dining", "room service", "food to my room"),
    "dining_reservation_request": ("table reservation", "book a table", "reserve a table"),
    "dining_food_order_request": ("order food", "place an order", "i want to order"),
    "dining_public_guest_enquiry": ("non-resident dining", "can outsiders eat", "walk-in guest"),
    # Activities
    "activity_spa_enquiry": ("spa", "massage", "wellness treatment", "ayurveda"),
    "activity_general_enquiry": ("activities", "things to do", "experiences"),
    "activity_pool_enquiry": ("swimming pool", "pool timing", "infinity pool"),
    "activity_kids_facilities": ("kids club", "children's activities", "kid friendly"),
    "activity_events_enquiry": ("event", "conference", "meeting space", "banquet"),
    "activity_wedding_enquiry": ("wedding", "get married", "wedding venue"),
    "activity_experiences_enquiry": ("nature walk", "adventure sport", "local experience", "excursion"),
    "activity_timings_enquiry": ("what time does it open", "opening hours", "timings"),
    "activity_price_enquiry": ("how much does the spa cost", "activity price", "cost of the treatment"),
    "activity_availability_enquiry": ("is the spa available", "can i book a slot"),
    # Transport
    "transport_airport_transfer": ("airport transfer", "airport pickup", "transfer from airport"),
    "transport_local": ("local transport", "getting around", "local taxi"),
    "transport_pickup_request": ("pick me up", "pickup request", "send a car"),
    "transport_drop_request": ("drop me", "drop-off", "take me to the airport"),
    "transport_vehicle_type": ("what kind of vehicle", "car type", "muv", "sedan"),
    "transport_pricing": ("transfer cost", "transport price", "how much is the transfer"),
    "transport_schedule": ("transfer schedule", "what time is the transfer"),
    # Billing/policy
    "billing_payment_methods": ("payment method", "how can i pay", "accept credit card", "upi"),
    "billing_deposit": ("deposit", "advance payment", "security deposit"),
    "billing_taxes": ("tax", "gst", "service charge"),
    "billing_invoice": ("invoice", "receipt", "bill copy"),
    "billing_refund": ("refund", "money back", "reimbursement"),
    "billing_cancellation_charges": ("cancellation charge", "cancellation fee", "penalty for cancelling"),
    "billing_damage_policy": ("damage policy", "damage charges", "broken item"),
    "policy_guest_policy": ("guest policy", "visitor policy", "id proof"),
    "policy_pet_policy": ("pet policy", "bring my dog", "pets allowed"),
    "policy_smoking_policy": ("smoking policy", "smoking allowed", "smoking area"),
    "policy_child_policy": ("child policy", "kids stay free", "child age policy"),
    # Support
    "support_complaint": ("complaint", "not happy", "disappointed", "unacceptable"),
    "support_service_issue": ("not working", "broken", "issue with my room", "problem with"),
    "support_emergency": ("emergency", "help now", "urgent help"),
    "support_safety_concern": ("safety concern", "feel unsafe", "security issue"),
    "support_medical_concern": ("medical emergency", "need a doctor", "not feeling well", "injury"),
    "support_lost_and_found": ("lost and found", "lost my", "left my", "missing item"),
    "support_human_agent_request": ("speak to a human", "talk to staff", "real person", "human agent"),
    "support_negotiation": ("can you lower the price", "negotiate", "better price", "discount please"),
    "support_exception_request": ("make an exception", "special case", "waive the policy"),
    "support_sensitive_payment_issue": ("payment failed", "charged twice", "unauthorized charge"),
}


def _tokenize(text: str) -> set[str]:
    return set(_WORD_PATTERN.findall(text.lower()))


def _score_intents(text: str) -> list[tuple[str, float]]:
    lowered = text.lower()
    scores: dict[str, float] = {}
    for intent, phrases in _INTENT_KEYWORDS.items():
        matches = sum(1 for phrase in phrases if phrase in lowered)
        if matches:
            scores[intent] = min(1.0, matches / 2.0)
    return sorted(scores.items(), key=lambda pair: pair[1], reverse=True)


_SMALL_TALK_MAX_LENGTH = 25  # a message that merely starts with "hello" but goes on to make a
# real request ("Hello, I need help with a booking") must not be classified as small talk —
# real bug caught by a unit test: startswith() alone matched any greeting-prefixed request.


def is_small_talk(text: str) -> bool:
    normalized = re.sub(r"[^\w\s]", "", text.lower()).strip()
    if len(normalized) > _SMALL_TALK_MAX_LENGTH:
        return False
    return any(normalized == phrase or normalized.startswith(phrase) for phrase in _SMALL_TALK_PHRASES)


def classify_intent_deterministic(text: str) -> DetectedIntent:
    if is_small_talk(text):
        return DetectedIntent(primary_intent="small_talk", confidence=0.9, is_small_talk=True)

    ranked = _score_intents(text)
    if not ranked:
        return DetectedIntent(primary_intent="unknown", confidence=0.0)

    primary_intent, primary_score = ranked[0]
    secondary = [(intent, score) for intent, score in ranked[1:] if score >= _SECONDARY_INTENT_THRESHOLD]
    return DetectedIntent(primary_intent=primary_intent, confidence=primary_score, secondary_intents=secondary)


async def classify_intent(text: str, *, llm_provider: LLMProvider | None = None) -> DetectedIntent:
    """The single entry point orchestration code calls (functions.md's
    detect_guest_intent). Escalates to the LLM only when deterministic
    confidence is low and a provider is actually supplied — callers that
    don't pass one (e.g. most unit tests) always get the pure deterministic
    path, never a network call."""
    deterministic = classify_intent_deterministic(text)
    if llm_provider is None or deterministic.confidence >= _LLM_ESCALATION_THRESHOLD:
        return deterministic

    try:
        return await _classify_with_llm(text, llm_provider, fallback=deterministic)
    except LLMProviderError:
        return deterministic


async def _classify_with_llm(text: str, llm_provider: LLMProvider, *, fallback: DetectedIntent) -> DetectedIntent:
    prompt = (
        "Classify the guest message into exactly one of these intents: "
        f"{', '.join(ALL_INTENTS)}.\n"
        'Respond with strict JSON: {"intent": "<one of the list>", "confidence": <0-1>}.\n'
        f"Guest message: {text}"
    )
    result = await llm_provider.complete(
        [
            LLMMessage(role="system", content="You are an intent classifier. Only output the requested JSON."),
            LLMMessage(role="user", content=prompt),
        ],
        response_format={"type": "json_object"},
        max_tokens=100,  # a JSON {"intent", "confidence"} object never needs more than this
    )
    try:
        parsed = json.loads(result.text)
        intent = parsed.get("intent")
        confidence = float(parsed.get("confidence", 0.5))
    except (json.JSONDecodeError, TypeError, ValueError):
        return fallback

    if intent not in ALL_INTENTS:
        return fallback

    return DetectedIntent(primary_intent=intent, confidence=confidence, secondary_intents=fallback.secondary_intents)
