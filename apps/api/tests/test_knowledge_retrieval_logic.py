"""Pure-logic tests for query classification, reranking, and the
governance scoring boost — no database required.
"""

from app.knowledge.models import KnowledgeChunk
from app.knowledge.retrieval.hybrid import RetrievedChunk, _governance_boost
from app.knowledge.retrieval.query_classification import classify_query
from app.knowledge.retrieval.reranker import HeuristicReranker


def _chunk(**overrides) -> KnowledgeChunk:
    defaults = dict(
        chunk_type="generic",
        content_normalized="Some resort content.",
        source_priority="normal",
        authoritative=False,
        section_title=None,
        entity_metadata={},
    )
    defaults.update(overrides)
    return KnowledgeChunk(**defaults)


# --- query classification --------------------------------------------------


def test_classify_query_detects_pricing():
    assert classify_query("How much does a couple massage cost?") == "pricing"


def test_classify_query_detects_room():
    assert classify_query("Tell me about the Deluxe Suite occupancy") == "room"


def test_classify_query_falls_back_to_general():
    assert classify_query("Tell me something interesting") == "general"


# --- governance boost -------------------------------------------------------


def test_critical_priority_scores_higher_than_low():
    critical = _governance_boost(_chunk(source_priority="critical"), "check-in time")
    low = _governance_boost(_chunk(source_priority="low"), "check-in time")
    assert critical > low


def test_authoritative_flag_adds_boost():
    plain = _governance_boost(_chunk(authoritative=False), "check-in time")
    authoritative = _governance_boost(_chunk(authoritative=True), "check-in time")
    assert authoritative > plain


def test_entity_metadata_match_adds_boost():
    query = "What is the rate for the Deluxe Suite?"
    with_match = _governance_boost(_chunk(entity_metadata={"Room Type": "Deluxe Suite"}), query)
    without_match = _governance_boost(_chunk(entity_metadata={"Room Type": "Garden Villa"}), query)
    assert with_match > without_match


# --- reranker ---------------------------------------------------------------


def test_heuristic_reranker_boosts_exact_keyword_overlap():
    high_overlap = RetrievedChunk(
        chunk=_chunk(content_normalized="The infinity pool closes at 9 PM daily."),
        dense_score=0.5, sparse_score=0.0, final_score=0.5,
    )
    low_overlap = RetrievedChunk(
        chunk=_chunk(content_normalized="Spa treatments require advance booking."),
        dense_score=0.5, sparse_score=0.0, final_score=0.5,
    )

    reranked = HeuristicReranker().rerank("what time does the pool close", [low_overlap, high_overlap])

    assert reranked[0] is high_overlap


def test_heuristic_reranker_handles_empty_query():
    result = RetrievedChunk(chunk=_chunk(), dense_score=0.1, sparse_score=0.1, final_score=0.2)
    reranked = HeuristicReranker().rerank("", [result])
    assert reranked == [result]
