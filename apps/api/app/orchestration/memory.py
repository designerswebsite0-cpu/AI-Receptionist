"""Controlled Customer 360 memory layer — rules.md §6: verified facts, AI
inferences, AI summaries, and conversation state are stored and read back
*separately*. An AI inference can never silently overwrite a verified,
staff-authored fact (`CustomerNote` / `Customer.full_name` etc. stay
human-only), and only a fixed, curated vocabulary of durable guest
preferences is ever written — never arbitrary free text from
`ExtractedEntities`. This is the "controlled" in "controlled memory
strategy", not unrestricted AI memory.

Conversation state itself already has its own durable home
(`Conversation.current_state`/`flow_state`, `ConversationStateEvent`) and
AI-generated handoff summaries already have theirs
(`app.orchestration.handoff.engine.summarize_conversation_for_staff`) — this
module's only job is the Customer 360 read/write path.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.customers import repository as customers_repository
from app.customers.models import Customer
from app.orchestration.domain import ExtractedEntities

# Durable, transferable-across-conversations guest preferences only —
# deliberately NOT the full ENTITY_FIELDS vocabulary. Stay-specific details
# (check_in_date, num_nights, booking_reference, ...) are correct for *this*
# stay/enquiry but would be actively wrong if "remembered" into some future,
# unrelated stay, so they are never written here.
DURABLE_MEMORY_FIELDS = (
    "guest_name",
    "language",
    "dietary_restrictions",
    "allergies",
    "view_preference",
    "room_category",
    "accessibility_needs",
    "meal_plan",
)

_AI_INFERENCE_NAMESPACE = "ai_inferred"
_MIN_CONFIDENCE_TO_STORE = 0.6


def _ai_inferences(customer: Customer) -> dict:
    return dict((customer.resort_preferences or {}).get(_AI_INFERENCE_NAMESPACE, {}))


async def record_inferences(
    db: AsyncSession, *, customer: Customer, entities: ExtractedEntities, conversation_id: uuid.UUID
) -> list[str]:
    """Write path. Persists newly-observed durable guest facts as AI
    inferences — never as verified data, never into CustomerNote, and only
    for fields in DURABLE_MEMORY_FIELDS. Below-confidence facts are
    silently skipped rather than recorded on weak evidence. A later
    conversation's inference for the same field overwrites the earlier one
    (guests are allowed to change their mind — recency wins, not a
    confidence contest), but this only ever touches the ai_inferred
    namespace, never `customer.full_name`/`preferred_language`/notes.
    """
    recorded: list[str] = []
    preferences = dict(customer.resort_preferences or {})
    inferences = dict(preferences.get(_AI_INFERENCE_NAMESPACE, {}))

    for field in DURABLE_MEMORY_FIELDS:
        value = entities.get(field)
        if value is None:
            continue
        confidence = entities.confidence.get(field, 0.0)
        if confidence < _MIN_CONFIDENCE_TO_STORE:
            continue
        inferences[field] = {
            "value": value,
            "confidence": confidence,
            "source": entities.source.get(field, "unknown"),
            "conversation_id": str(conversation_id),
            "recorded_at": datetime.now(UTC).isoformat(),
        }
        recorded.append(field)

    if recorded:
        preferences[_AI_INFERENCE_NAMESPACE] = inferences
        customer.resort_preferences = preferences
        await db.commit()

    return recorded


async def assemble_memory_context(db: AsyncSession, *, customer: Customer) -> dict:
    """Read path: verified facts and AI inferences as clearly separated
    buckets. Callers (e.g. context assembly / a future staff-facing memory
    view) must never present an inference to the model or to staff as if
    it were verified — the separation is the whole point."""
    notes = await customers_repository.list_notes(db, customer.id)
    return {
        "verified": {
            "full_name": customer.full_name,
            "preferred_language": customer.preferred_language,
            "loyalty_reference": customer.loyalty_reference,
            "staff_notes": [note.note for note in notes],
        },
        "ai_inferred": _ai_inferences(customer),
    }
