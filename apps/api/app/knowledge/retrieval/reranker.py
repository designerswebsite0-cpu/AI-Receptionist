"""Reranking — a cheap lexical-overlap pass applied after hybrid scoring.
No dedicated reranking model/API is wired up (out of scope for this
phase per the brief's "minimal answer composer" boundary); this heuristic
still meaningfully improves ordering when a query uses exact terminology
present in one candidate but not others (e.g. a specific room or dish
name), which cosine similarity alone can under-weight.
"""

import re

from app.knowledge.retrieval.hybrid import RetrievedChunk

_WORD_PATTERN = re.compile(r"[a-z0-9]+")
_OVERLAP_BOOST = 0.10


class Reranker:
    def rerank(self, query_text: str, results: list[RetrievedChunk]) -> list[RetrievedChunk]:
        raise NotImplementedError


class HeuristicReranker(Reranker):
    def rerank(self, query_text: str, results: list[RetrievedChunk]) -> list[RetrievedChunk]:
        query_terms = set(_WORD_PATTERN.findall(query_text.lower()))
        if not query_terms:
            return results

        for retrieved in results:
            content_terms = set(_WORD_PATTERN.findall(retrieved.chunk.content_normalized.lower()))
            overlap_ratio = len(query_terms & content_terms) / len(query_terms)
            retrieved.final_score += overlap_ratio * _OVERLAP_BOOST

        return sorted(results, key=lambda r: r.final_score, reverse=True)
