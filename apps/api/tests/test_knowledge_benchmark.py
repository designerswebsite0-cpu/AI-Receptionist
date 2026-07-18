"""Integration test for app.knowledge.benchmark — requires a reachable
Postgres with pgvector (see conftest.db_engine); skips cleanly when none
is available. Uses MockEmbeddingProvider, never the real OpenAI API.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge import service
from app.knowledge.benchmark import run_benchmark
from app.knowledge.embeddings import MockEmbeddingProvider
from app.knowledge.extraction.base import ExtractedContent
from app.knowledge.indexing import index_source_version
from app.knowledge.models import KnowledgeBenchmarkQuestion
from app.knowledge.retrieval.reranker import HeuristicReranker
from app.knowledge.schemas import SourceRegisterRequest


async def _seed_activated_source(db: AsyncSession, *, text: str):
    source = await service.register_source(
        db, body=SourceRegisterRequest(title="Policy Source", source_type="document", visibility="guest"),
        actor_user_id=None,
    )
    version = await service.record_source_version(
        db, source_id=source.id, checksum_sha256="e" * 64, storage_path=None, actor_user_id=None
    )
    extracted = ExtractedContent(raw_text=text, extraction_method="plain-text", word_count=len(text.split()))
    await index_source_version(
        db, source=source, version=version, extracted=extracted, provider=MockEmbeddingProvider()
    )
    await service.approve_source(db, source_id=source.id, actor_user_id=None)
    source = await service.get_source_or_404(db, source.id)
    source.processing_status = "completed"
    source.malware_scan_status = "clean"
    await db.commit()
    await service.activate_source(db, source_id=source.id, actor_user_id=None)


@pytest.mark.asyncio
async def test_benchmark_scores_a_question_with_matching_content(db_session: AsyncSession):
    await _seed_activated_source(
        db_session, text="Q: What time is check-in? A: Check-in begins at 2:00 PM daily for all guests."
    )
    question = KnowledgeBenchmarkQuestion(
        question="What time is check-in?",
        expected_answer="Check-in begins at 2:00 PM",
        audience="guest",
        priority="high",
    )
    db_session.add(question)
    await db_session.commit()

    summary = await run_benchmark(
        db_session, embedding_provider=MockEmbeddingProvider(), reranker=HeuristicReranker()
    )

    assert summary.total == 1
    assert summary.passed == 1
    assert summary.results[0].overlap_ratio > 0.35

    await db_session.refresh(question)
    assert question.last_run_result is not None
    assert question.last_run_result["passed"] is True
    assert question.last_run_at is not None


@pytest.mark.asyncio
async def test_benchmark_fails_a_question_with_no_matching_content(db_session: AsyncSession):
    await _seed_activated_source(db_session, text="The infinity pool is open from 7 AM to 9 PM.")
    question = KnowledgeBenchmarkQuestion(
        question="How much does a couple massage cost?",
        expected_answer="Couple spa rituals start from INR 11,800 for two guests",
        audience="guest",
        priority="normal",
    )
    db_session.add(question)
    await db_session.commit()

    summary = await run_benchmark(
        db_session, embedding_provider=MockEmbeddingProvider(), reranker=HeuristicReranker()
    )

    assert summary.total == 1
    assert summary.passed == 0
    assert summary.failed == 1
    assert summary.pass_rate == 0.0


@pytest.mark.asyncio
async def test_benchmark_by_category_breakdown(db_session: AsyncSession):
    await _seed_activated_source(db_session, text="Check-in begins at 2:00 PM daily.")
    db_session.add(
        KnowledgeBenchmarkQuestion(
            question="What time is check-in?", expected_answer="Check-in begins at 2:00 PM",
            category="Policies", audience="guest", priority="high",
        )
    )
    db_session.add(
        KnowledgeBenchmarkQuestion(
            question="How much is the couple massage?", expected_answer="INR 11,800 for two guests",
            category="Spa", audience="guest", priority="normal",
        )
    )
    await db_session.commit()

    summary = await run_benchmark(
        db_session, embedding_provider=MockEmbeddingProvider(), reranker=HeuristicReranker()
    )

    breakdown = summary.by_category
    assert breakdown["Policies"]["passed"] == 1
    assert breakdown["Spa"]["failed"] == 1
