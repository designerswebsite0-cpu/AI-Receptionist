"""Top-level retrieval orchestration: classify -> embed query -> hybrid
search -> rerank -> assemble citations -> log. This is the one entry
point every caller (dashboard search playground, benchmark runner, future
answer composer) should use — none of them should call hybrid_search
directly, since that would skip logging and citation redaction.
"""

import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge import repository
from app.knowledge.embeddings import EmbeddingProvider
from app.knowledge.retrieval.hybrid import RetrievedChunk, hybrid_search
from app.knowledge.retrieval.query_classification import classify_query
from app.knowledge.retrieval.reranker import Reranker
from app.knowledge.schemas import CitationOut, SearchResponse


def _to_citation(retrieved: RetrievedChunk, source) -> CitationOut:
    chunk = retrieved.chunk
    return CitationOut(
        chunk_id=chunk.id,
        content=chunk.content_normalized,
        chunk_type=chunk.chunk_type,
        section_title=chunk.section_title,
        page_number=chunk.page_number,
        source_id=source.id,
        source_external_id=source.source_id,
        source_title=source.title,
        source_priority=chunk.source_priority,
        authoritative=chunk.authoritative,
        version_number=None,
        effective_date=chunk.effective_date,
        # A website source has one source_url (the site root) but each
        # chunk belongs to a distinct crawled page — prefer the chunk's
        # own page_url (set by app.knowledge.website.service) when present
        # so a citation points at the actual page the content came from.
        source_url=chunk.entity_metadata.get("page_url") or source.source_url,
        score=round(retrieved.final_score, 4),
    )


async def search(
    db: AsyncSession,
    *,
    query_text: str,
    embedding_provider: EmbeddingProvider,
    reranker: Reranker,
    guest_only: bool = True,
    limit: int = 10,
    chunk_type: str | None = None,
    conversation_id: uuid.UUID | None = None,
    requested_channel: str | None = None,
    requested_by: uuid.UUID | None = None,
) -> SearchResponse:
    started_at = time.monotonic()

    classification = classify_query(query_text)
    [embedding] = await embedding_provider.embed_batch([query_text])

    retrieved = await hybrid_search(
        db,
        query_text=query_text,
        query_vector=embedding.vector,
        guest_only=guest_only,
        limit=limit,
        # classification is logged for analytics but never used to filter
        # results — its categories ("pricing", "dining") don't map 1:1
        # onto chunk_type values ("room_rate", "menu_item"), so treating
        # it as a hard filter would silently exclude valid matches.
        chunk_type=chunk_type,
    )
    retrieved = reranker.rerank(query_text, retrieved)

    source_ids = list({r.chunk.source_id for r in retrieved})
    sources_by_id = await repository.get_sources_by_ids(db, source_ids)
    citations = [
        _to_citation(r, sources_by_id[r.chunk.source_id]) for r in retrieved if r.chunk.source_id in sources_by_id
    ]

    latency_ms = int((time.monotonic() - started_at) * 1000)
    log = await repository.create_retrieval_log(
        db,
        query_text=query_text,
        query_classification=classification,
        filters_applied={"guest_only": guest_only, "chunk_type": chunk_type, "limit": limit},
        results_returned=[{"chunk_id": str(c.chunk_id), "score": c.score} for c in citations],
        latency_ms=latency_ms,
        requested_channel=requested_channel,
        conversation_id=conversation_id,
        requested_by=requested_by,
    )

    return SearchResponse(
        query=query_text,
        query_classification=classification,
        results=citations,
        retrieval_log_id=log.id,
        latency_ms=latency_ms,
    )
