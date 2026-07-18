"""Pure data — no engine imports, mirrors app.conversations.constants'
pattern. Intent taxonomy is resort-specific (docs/Goal.md) but the
orchestration pipeline itself (app.orchestration.pipeline) is channel- and
vertical-neutral per architecture.md §4.4 — a future non-resort deployment
swaps this file and the knowledge base, not the pipeline.
"""

# --- Intent taxonomy ---------------------------------------------------------
# Grouped for readability; ALL_INTENTS is the flat set actually validated
# against. "small_talk" and "unknown" are not resort-domain intents but are
# real, expected classifier outputs (functions.md §28 detect_small_talk).

GENERAL_INTENTS = (
    "general_resort_overview",
    "general_location_directions",
    "general_contact_info",
    "general_checkin_checkout",
    "general_amenities",
    "general_accessibility",
    "general_wifi",
    "general_weather",
    "general_policy",
)

ROOM_INTENTS = (
    "room_category_enquiry",
    "room_villa_enquiry",
    "room_occupancy_enquiry",
    "room_bed_configuration",
    "room_view_preference",
    "room_private_pool_enquiry",
    "room_accessibility_requirements",
    "room_extra_bed_request",
    "room_connecting_request",
    "room_availability_enquiry",
    "room_price_enquiry",
    "room_offer_enquiry",
    "room_booking_request",
    "room_modification_request",
    "room_cancellation_request",
)

DINING_INTENTS = (
    "dining_restaurant_info",
    "dining_menu_enquiry",
    "dining_dietary_requirement",
    "dining_allergen_enquiry",
    "dining_in_room_dining",
    "dining_reservation_request",
    "dining_food_order_request",
    "dining_public_guest_enquiry",
)

ACTIVITY_INTENTS = (
    "activity_spa_enquiry",
    "activity_general_enquiry",
    "activity_pool_enquiry",
    "activity_kids_facilities",
    "activity_events_enquiry",
    "activity_wedding_enquiry",
    "activity_experiences_enquiry",
    "activity_timings_enquiry",
    "activity_price_enquiry",
    "activity_availability_enquiry",
)

TRANSPORT_INTENTS = (
    "transport_airport_transfer",
    "transport_local",
    "transport_pickup_request",
    "transport_drop_request",
    "transport_vehicle_type",
    "transport_pricing",
    "transport_schedule",
)

BILLING_POLICY_INTENTS = (
    "billing_payment_methods",
    "billing_deposit",
    "billing_taxes",
    "billing_invoice",
    "billing_refund",
    "billing_cancellation_charges",
    "billing_damage_policy",
    "policy_guest_policy",
    "policy_pet_policy",
    "policy_smoking_policy",
    "policy_child_policy",
)

SUPPORT_INTENTS = (
    "support_complaint",
    "support_service_issue",
    "support_emergency",
    "support_safety_concern",
    "support_medical_concern",
    "support_lost_and_found",
    "support_human_agent_request",
    "support_negotiation",
    "support_exception_request",
    "support_sensitive_payment_issue",
)

META_INTENTS = ("small_talk", "unknown")

ALL_INTENTS = (
    GENERAL_INTENTS
    + ROOM_INTENTS
    + DINING_INTENTS
    + ACTIVITY_INTENTS
    + TRANSPORT_INTENTS
    + BILLING_POLICY_INTENTS
    + SUPPORT_INTENTS
    + META_INTENTS
)

# Intents that mandate human handoff regardless of confidence — see
# app.orchestration.handoff.engine. Never overridable by the LLM.
MANDATORY_HANDOFF_INTENTS = (
    "billing_refund",
    "support_emergency",
    "support_safety_concern",
    "support_medical_concern",
    "support_sensitive_payment_issue",
    "support_human_agent_request",
    "support_negotiation",
    "support_exception_request",
    "room_cancellation_request",
)

# --- Entity taxonomy (functions.md §28 extract_guest_entities, extended
# with the Phase 4 brief's stay/transfer-specific fields) -------------------

ENTITY_FIELDS = (
    "guest_name",
    "phone",
    "email",
    "check_in_date",
    "check_out_date",
    "num_nights",
    "adults",
    "children",
    "child_ages",
    "room_category",
    "num_rooms",
    "budget",
    "meal_plan",
    "dietary_restrictions",
    "allergies",
    "view_preference",
    "occasion",
    "accessibility_needs",
    "activity",
    "spa_service",
    "transfer_origin",
    "transfer_destination",
    "arrival_details",
    "departure_details",
    "booking_reference",
    "language",
    "urgency",
)

# --- Flow states (refinement WITHIN a canonical DIALOGUE_STATE — see
# app.conversations.constants.DIALOGUE_STATES, which this does NOT replace;
# reconciliation documented in docs/phase-4/PHASE_4_IMPLEMENTATION_PLAN.md §1) -

FLOW_STATES_BY_DIALOGUE_STATE: dict[str, tuple[str, ...]] = {
    "greeting": ("new_conversation",),
    "discovering_needs": ("general_enquiry", "dining_enquiry", "activity_enquiry", "transfer_enquiry"),
    "collecting_information": (
        "collecting_stay_details",
        "collecting_guest_details",
        "restaurant_order_collection",
        "transfer_detail_collection",
    ),
    "recommending": ("comparing_rooms",),
    "booking": (
        "booking_assistance",
        "modification_request",
        "cancellation_request",
    ),
    "waiting": (
        "awaiting_availability_verification",
        "awaiting_price_verification",
        "awaiting_staff_confirmation",
    ),
    "confirmation": ("awaiting_staff_confirmation",),
    "upselling": ("upsell_offer",),
    "support": ("complaint_handling",),
    "escalation": (
        "emergency_escalation",
        "human_handoff_requested",
        "human_handoff_active",
    ),
    "closed": ("resolved", "closed"),
}

ALL_FLOW_STATES = tuple({state for states in FLOW_STATES_BY_DIALOGUE_STATE.values() for state in states})

# --- Handoff --------------------------------------------------------------

HANDOFF_PRIORITIES = ("low", "normal", "high", "urgent")

HANDOFF_DEPARTMENTS = (
    "front_desk",
    "reservations",
    "dining",
    "spa_activities",
    "transport",
    "billing",
    "security_safety",
    "management",
)

HANDOFF_REASON_CODES = (
    "payment_collection",
    "payment_failure",
    "refund_request",
    "booking_confirmation_required",
    "cancellation_execution",
    "price_negotiation",
    "policy_exception",
    "legal_threat",
    "safety_incident",
    "medical_emergency",
    "security_concern",
    "harassment_or_abuse",
    "high_risk_complaint",
    "lost_valuables",
    "unverified_availability",
    "conflicting_knowledge_sources",
    "explicit_human_request",
    "repeated_low_confidence",
    "repeated_tool_failure",
    "provider_failure",
    "retrieval_insufficient_for_sensitive_answer",
)

# --- Tool / service-request taxonomy ---------------------------------------

SERVICE_REQUEST_TYPES = (
    "booking_enquiry",
    "dining_enquiry",
    "spa_enquiry",
    "activity_enquiry",
    "transfer_enquiry",
    "service_request",
    "complaint",
)

SERVICE_REQUEST_STATUSES = ("open", "in_progress", "resolved", "cancelled")

TOOL_PERMISSION_LEVELS = ("guest_safe", "requires_guest_confirmation", "requires_staff_approval")
