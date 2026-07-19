"""Token-budgeted, source-attributed context assembly. Produces facts
only (guest message, recent turns, guest profile, retrieved knowledge) —
how those facts get phrased for the model is app.orchestration.prompts'
job, kept deliberately separate.

Reuses app.knowledge.chunking.strategies.count_tokens (tiktoken-based,
already built in Phase 3) rather than re-implementing token counting, and
app.knowledge.retrieval.service.search for retrieval — this module never
queries knowledge_chunks directly.
"""

import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.customers.models import Customer
from app.knowledge.chunking.strategies import count_tokens
from app.knowledge.embeddings import EmbeddingProvider
from app.knowledge.retrieval import service as retrieval_service
from app.knowledge.retrieval.reranker import Reranker
from app.knowledge.schemas import SearchResponse
from app.messages import repository as messages_repository
from app.orchestration.domain import RetrievedCitation, RetrievedContext

_RECENT_MESSAGE_LIMIT = 10
_GUEST_PROFILE_TOKEN_RESERVE = 150
_RETRIEVAL_LIMIT = 8

# Never truncated away regardless of budget pressure — dropping a
# critical/authoritative citation to make room for conversation history
# would be exactly the "silently remove critical policy information"
# failure mode the brief explicitly forbids.
_NEVER_TRUNCATE_PRIORITIES = {"critical"}


@dataclass
class ConversationTurn:
    role: str  # "customer" | "ai" | "human" | "system"
    content: str


@dataclass
class AssembledContext:
    guest_message: str
    recent_turns: list[ConversationTurn] = field(default_factory=list)
    dialogue_state: str = "greeting"
    flow_state: str | None = None
    guest_profile: dict = field(default_factory=dict)
    stated_entities: dict = field(default_factory=dict)
    date_validation_issues: list[str] = field(default_factory=list)
    retrieved_context: RetrievedContext = field(default_factory=lambda: RetrievedContext(query=""))
    truncated: bool = False
    total_tokens_estimate: int = 0


def _sanitize_guest_profile(customer: Customer | None) -> dict:
    """Only facts useful for personalization — never staff notes, never
    raw contact values beyond what's already been given by the guest in
    this conversation, never internal identifiers.

    Verified (staff-set) preferences and the AI's own past inferences
    (app.orchestration.memory.record_inferences writes into the
    "ai_inferred" sub-key) are kept in separate profile keys — rules.md §6
    requires an AI inference never be presented to the model as if it were
    a staff-confirmed fact, so the two are labeled distinctly rather than
    flattened into one "resort_preferences" blob.
    """
    if customer is None:
        return {}
    profile = {
        "full_name": customer.full_name,
        "preferred_language": customer.preferred_language,
        "loyalty_reference": customer.loyalty_reference,
    }
    preferences = dict(customer.resort_preferences or {})
    ai_inferred = preferences.pop("ai_inferred", None)
    if preferences:
        profile["confirmed_preferences"] = preferences
    if ai_inferred:
        profile["ai_noted_preferences_unconfirmed"] = {
            field: entry.get("value") for field, entry in ai_inferred.items()
        }
    return {key: value for key, value in profile.items() if value}


def _trim_citations_to_budget(
    citations: list[RetrievedCitation], *, max_tokens: int
) -> tuple[list[RetrievedCitation], bool]:
    protected = [c for c in citations if c.source_priority in _NEVER_TRUNCATE_PRIORITIES]
    optional = [c for c in citations if c.source_priority not in _NEVER_TRUNCATE_PRIORITIES]

    kept: list[RetrievedCitation] = []
    used_tokens = 0
    truncated = False

    for citation in protected + optional:
        citation_tokens = count_tokens(citation.content)
        if citation in protected or used_tokens + citation_tokens <= max_tokens:
            kept.append(citation)
            used_tokens += citation_tokens
        else:
            truncated = True

    # Restore original relevance ordering (protected citations were moved
    # to the front above only to guarantee their inclusion, not to
    # reorder the final context).
    kept_ids = {c.chunk_id for c in kept}
    ordered = [c for c in citations if c.chunk_id in kept_ids]
    return ordered, truncated


def _trim_turns_to_budget(turns: list[ConversationTurn], *, max_tokens: int) -> tuple[list[ConversationTurn], bool]:
    """Recency-weighted: drops the OLDEST turns first when over budget."""
    kept: list[ConversationTurn] = []
    used_tokens = 0
    truncated = False
    for turn in reversed(turns):  # most recent first
        turn_tokens = count_tokens(turn.content)
        if used_tokens + turn_tokens > max_tokens:
            truncated = True
            break
        kept.insert(0, turn)
        used_tokens += turn_tokens
    if len(kept) < len(turns):
        truncated = True
    return kept, truncated


async def assemble_context(
    db: AsyncSession,
    *,
    conversation_id: uuid.UUID,
    customer: Customer | None,
    guest_message: str,
    dialogue_state: str,
    flow_state: str | None,
    embedding_provider: EmbeddingProvider,
    reranker: Reranker,
    guest_only: bool = True,
    max_tokens: int | None = None,
    search_response: SearchResponse | None = None,
    stated_entities: dict | None = None,
    date_validation_issues: list[str] | None = None,
) -> AssembledContext:
    settings = get_settings()
    budget = max_tokens or settings.orchestration_max_context_tokens

    guest_profile = _sanitize_guest_profile(customer)
    remaining_budget = budget - _GUEST_PROFILE_TOKEN_RESERVE

    # The retrieval query only ever depends on guest_message (never on
    # dialogue_state/flow_state, which just get stored on the returned
    # AssembledContext) — callers on the hot path (app.orchestration.
    # pipeline) fetch this concurrently with intent/entity classification
    # and pass it in, rather than paying for it here, serialized after
    # those calls already completed.
    if search_response is None:
        search_response = await retrieval_service.search(
            db,
            query_text=guest_message,
            embedding_provider=embedding_provider,
            reranker=reranker,
            guest_only=guest_only,
            limit=_RETRIEVAL_LIMIT,
            conversation_id=conversation_id,
            requested_channel="orchestration",
        )
    citations = [
        RetrievedCitation(
            chunk_id=c.chunk_id,
            content=c.content,
            source_title=c.source_title,
            source_priority=c.source_priority,
            authoritative=c.authoritative,
            score=c.score,
            source_url=c.source_url,
        )
        for c in search_response.results
    ]

    # Reserve roughly 60% of the remaining budget for retrieved knowledge,
    # 40% for conversation history — knowledge grounding matters more than
    # recalling exact chat history, but neither is starved to zero.
    retrieval_budget = int(remaining_budget * 0.6)
    history_budget = remaining_budget - retrieval_budget

    trimmed_citations, citations_truncated = _trim_citations_to_budget(citations, max_tokens=retrieval_budget)

    recent_messages = await messages_repository.list_recent_messages(db, conversation_id, limit=_RECENT_MESSAGE_LIMIT)
    turns = [
        ConversationTurn(role=m.sender_type, content=m.content_text)
        for m in recent_messages
        if m.content_text and m.content_text.strip()
    ]
    trimmed_turns, turns_truncated = _trim_turns_to_budget(turns, max_tokens=history_budget)

    retrieved_context = RetrievedContext(
        query=guest_message,
        citations=trimmed_citations,
        classification=search_response.query_classification,
        latency_ms=search_response.latency_ms,
    )

    total_tokens = (
        _GUEST_PROFILE_TOKEN_RESERVE
        + sum(count_tokens(c.content) for c in trimmed_citations)
        + sum(count_tokens(t.content) for t in trimmed_turns)
        + count_tokens(guest_message)
    )

    return AssembledContext(
        guest_message=guest_message,
        recent_turns=trimmed_turns,
        dialogue_state=dialogue_state,
        flow_state=flow_state,
        guest_profile=guest_profile,
        stated_entities=stated_entities or {},
        date_validation_issues=date_validation_issues or [],
        retrieved_context=retrieved_context,
        truncated=citations_truncated or turns_truncated,
        total_tokens_estimate=total_tokens,
    )
