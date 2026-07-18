"""Benchmark evaluation: runs every knowledge_benchmark_questions row
through the real retrieval pipeline and scores whether the expected
content was found. No LLM-judge is used — scoring is a lexical-overlap
heuristic between expected_answer and retrieved chunk content. This is
deliberate, not a shortcut: the brief explicitly draws the line at a
minimal search-testing composer this phase, not a full answer-generation
agent, so there is no LLM in the loop to ask "is this answer correct".
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge.embeddings import EmbeddingProvider
from app.knowledge.models import KnowledgeBenchmarkQuestion
from app.knowledge.retrieval import service as retrieval_service
from app.knowledge.retrieval.reranker import Reranker

_WORD_PATTERN = re.compile(r"[a-z0-9]+")
# Fraction of the expected answer's distinct keywords that must appear
# somewhere in the retrieved content for a question to count as passed.
# Chosen empirically low (not 0.8+) because a correct chunk paraphrases
# rather than quotes the expected answer verbatim — this heuristic proxies
# "the right content came back", not "the wording matches exactly".
_PASS_THRESHOLD = 0.35


@dataclass
class BenchmarkResult:
    question_id: str
    question: str
    category: str | None
    passed: bool
    overlap_ratio: float
    retrieved_source_titles: list[str]
    latency_ms: int


@dataclass
class BenchmarkSummary:
    total: int
    passed: int
    failed: int
    pass_rate: float
    average_latency_ms: float
    results: list[BenchmarkResult]

    @property
    def by_category(self) -> dict[str, dict[str, int]]:
        breakdown: dict[str, dict[str, int]] = {}
        for result in self.results:
            category = result.category or "uncategorized"
            bucket = breakdown.setdefault(category, {"passed": 0, "failed": 0})
            bucket["passed" if result.passed else "failed"] += 1
        return breakdown


def _overlap_ratio(expected_answer: str, retrieved_texts: list[str]) -> float:
    expected_terms = set(_WORD_PATTERN.findall(expected_answer.lower()))
    if not expected_terms:
        return 0.0
    combined = " ".join(retrieved_texts).lower()
    retrieved_terms = set(_WORD_PATTERN.findall(combined))
    return len(expected_terms & retrieved_terms) / len(expected_terms)


async def run_benchmark(
    db: AsyncSession,
    *,
    embedding_provider: EmbeddingProvider,
    reranker: Reranker,
    audience: str = "guest",
    limit_questions: int | None = None,
) -> BenchmarkSummary:
    stmt = select(KnowledgeBenchmarkQuestion).where(KnowledgeBenchmarkQuestion.audience == audience)
    if limit_questions:
        stmt = stmt.limit(limit_questions)
    questions = (await db.execute(stmt)).scalars().all()

    results: list[BenchmarkResult] = []
    total_latency = 0

    for question in questions:
        response = await retrieval_service.search(
            db,
            query_text=question.question,
            embedding_provider=embedding_provider,
            reranker=reranker,
            guest_only=(audience == "guest"),
            limit=5,
            requested_channel="benchmark",
        )
        total_latency += response.latency_ms

        retrieved_texts = [citation.content for citation in response.results]
        overlap = _overlap_ratio(question.expected_answer or "", retrieved_texts)
        passed = overlap >= _PASS_THRESHOLD

        question.last_run_result = {
            "overlap_ratio": round(overlap, 4),
            "passed": passed,
            "retrieved_chunk_ids": [str(c.chunk_id) for c in response.results],
            "retrieved_source_titles": [c.source_title for c in response.results],
        }
        question.last_run_at = datetime.now(UTC)

        results.append(
            BenchmarkResult(
                question_id=str(question.id),
                question=question.question,
                category=question.category,
                passed=passed,
                overlap_ratio=overlap,
                retrieved_source_titles=[c.source_title for c in response.results],
                latency_ms=response.latency_ms,
            )
        )

    await db.commit()

    total = len(results)
    passed_count = sum(1 for r in results if r.passed)
    return BenchmarkSummary(
        total=total,
        passed=passed_count,
        failed=total - passed_count,
        pass_rate=(passed_count / total) if total else 0.0,
        average_latency_ms=(total_latency / total) if total else 0.0,
        results=results,
    )
