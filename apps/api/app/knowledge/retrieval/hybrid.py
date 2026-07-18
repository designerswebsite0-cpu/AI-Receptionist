"""Hybrid retrieval: pgvector cosine similarity (dense) + PostgreSQL full
-text search (sparse), merged and scored with governance weighting.

Guest-safety is enforced here at the query level — every candidate query
filters on visibility/retrieval_enabled/status directly in its WHERE
clause, never as a Python post-filter (IMPLEMENTATION_PLAN.md §2). No
freshness boost exists anywhere in the scoring: archived/expired content
is excluded before scoring runs, not merely down-weighted.
"""

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge.models import KnowledgeChunk

_PRIORITY_BOOST = {"critical": 0.20, "high": 0.12, "normal": 0.0, "low": -0.05}
_AUTHORITATIVE_BOOST = 0.15
_ENTITY_MATCH_BOOST = 0.10
_SECTION_TITLE_MATCH_BOOST = 0.05

_DENSE_WEIGHT = 0.65
_SPARSE_WEIGHT = 0.35
_DENSE_CANDIDATES = 40
_SPARSE_CANDIDATES = 40


@dataclass
class RetrievedChunk:
    chunk: KnowledgeChunk
    dense_score: float
    sparse_score: float
    final_score: float


def _apply_guest_safety(stmt: Select, *, guest_only: bool) -> Select:
    today = date.today()
    stmt = stmt.where(
        KnowledgeChunk.status == "active",
        (KnowledgeChunk.expiry_date.is_(None)) | (KnowledgeChunk.expiry_date >= today),
    )
    if guest_only:
        stmt = stmt.where(KnowledgeChunk.visibility == "guest", KnowledgeChunk.retrieval_enabled.is_(True))
    return stmt


async def _dense_candidates(
    db: AsyncSession, query_vector: list[float], *, guest_only: bool, limit: int, chunk_type: str | None
) -> list[tuple[KnowledgeChunk, float]]:
    distance = KnowledgeChunk.embedding.cosine_distance(query_vector)
    stmt = select(KnowledgeChunk, distance.label("distance")).where(KnowledgeChunk.embedding.is_not(None))
    stmt = _apply_guest_safety(stmt, guest_only=guest_only)
    if chunk_type:
        stmt = stmt.where(KnowledgeChunk.chunk_type == chunk_type)
    stmt = stmt.order_by(distance).limit(limit)

    result = await db.execute(stmt)
    # pgvector's cosine_distance is 1 - cosine_similarity; converting back
    # to a similarity score keeps this module's scale consistent with the
    # sparse side (both roughly 0..1, higher is better).
    return [(row[0], 1.0 - float(row[1])) for row in result.all()]


async def _sparse_candidates(
    db: AsyncSession, query_text: str, *, guest_only: bool, limit: int
) -> list[tuple[KnowledgeChunk, float]]:
    tsvector = func.to_tsvector("english", KnowledgeChunk.content_normalized)
    tsquery = func.plainto_tsquery("english", query_text)
    rank = func.ts_rank(tsvector, tsquery)

    stmt = select(KnowledgeChunk, rank.label("rank")).where(tsvector.op("@@")(tsquery))
    stmt = _apply_guest_safety(stmt, guest_only=guest_only)
    stmt = stmt.order_by(rank.desc()).limit(limit)

    result = await db.execute(stmt)
    return [(row[0], float(row[1])) for row in result.all()]


def _governance_boost(chunk: KnowledgeChunk, query_text: str) -> float:
    boost = _PRIORITY_BOOST.get(chunk.source_priority, 0.0)
    if chunk.authoritative:
        boost += _AUTHORITATIVE_BOOST

    lowered_query = query_text.lower()
    if chunk.section_title and chunk.section_title.lower() in lowered_query:
        boost += _SECTION_TITLE_MATCH_BOOST
    if chunk.entity_metadata:
        for value in chunk.entity_metadata.values():
            if isinstance(value, str) and value.strip() and value.lower() in lowered_query:
                boost += _ENTITY_MATCH_BOOST
                break
    return boost


async def hybrid_search(
    db: AsyncSession,
    *,
    query_text: str,
    query_vector: list[float],
    guest_only: bool = True,
    limit: int = 10,
    chunk_type: str | None = None,
) -> list[RetrievedChunk]:
    dense = await _dense_candidates(
        db, query_vector, guest_only=guest_only, limit=_DENSE_CANDIDATES, chunk_type=chunk_type
    )
    sparse = await _sparse_candidates(db, query_text, guest_only=guest_only, limit=_SPARSE_CANDIDATES)

    merged: dict[uuid.UUID, RetrievedChunk] = {}
    for chunk, score in dense:
        merged[chunk.id] = RetrievedChunk(chunk=chunk, dense_score=score, sparse_score=0.0, final_score=0.0)
    for chunk, score in sparse:
        existing = merged.get(chunk.id)
        if existing:
            existing.sparse_score = score
        else:
            merged[chunk.id] = RetrievedChunk(chunk=chunk, dense_score=0.0, sparse_score=score, final_score=0.0)

    # ts_rank has no fixed upper bound, unlike cosine similarity — normalize
    # sparse scores within this result set so the two weighted terms are
    # on a comparable scale before combining.
    max_sparse = max((r.sparse_score for r in merged.values()), default=0.0) or 1.0

    for retrieved in merged.values():
        normalized_sparse = retrieved.sparse_score / max_sparse
        retrieved.final_score = (
            retrieved.dense_score * _DENSE_WEIGHT
            + normalized_sparse * _SPARSE_WEIGHT
            + _governance_boost(retrieved.chunk, query_text)
        )

    ranked = sorted(merged.values(), key=lambda r: r.final_score, reverse=True)
    return ranked[:limit]
