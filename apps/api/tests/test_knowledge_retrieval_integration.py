"""Integration tests for hybrid retrieval and the retrieval service —
requires a reachable Postgres with pgvector (see conftest.db_engine);
skips cleanly when none is available.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge import repository, service
from app.knowledge.embeddings import MockEmbeddingProvider
from app.knowledge.extraction.base import ExtractedContent
from app.knowledge.indexing import index_source_version
from app.knowledge.retrieval import service as retrieval_service
from app.knowledge.retrieval.hybrid import hybrid_search
from app.knowledge.retrieval.reranker import HeuristicReranker
from app.knowledge.schemas import SourceRegisterRequest


async def _seeded_source(db: AsyncSession, *, visibility: str, text: str, activate: bool = True):
    source = await service.register_source(
        db, body=SourceRegisterRequest(title="Seed Source", source_type="document", visibility=visibility),
        actor_user_id=None,
    )
    version = await service.record_source_version(
        db, source_id=source.id, checksum_sha256="9" * 64, storage_path=None, actor_user_id=None
    )
    extracted = ExtractedContent(raw_text=text, extraction_method="plain-text", word_count=len(text.split()))
    provider = MockEmbeddingProvider()
    await index_source_version(db, source=source, version=version, extracted=extracted, provider=provider)

    if activate:
        await service.approve_source(db, source_id=source.id, actor_user_id=None)
        source = await service.get_source_or_404(db, source.id)
        source.processing_status = "completed"
        source.malware_scan_status = "clean"
        await db.commit()
        await service.activate_source(db, source_id=source.id, actor_user_id=None)

    return source


@pytest.mark.asyncio
async def test_hybrid_search_excludes_staff_only_from_guest_query(db_session: AsyncSession):
    await _seeded_source(
        db_session, visibility="guest", text="The infinity pool is open from 7 AM to 9 PM daily."
    )
    await _seeded_source(
        db_session, visibility="staff", text="Staff-only note: pool maintenance runs Tuesdays 6-7 AM."
    )

    provider = MockEmbeddingProvider()
    [embedding] = await provider.embed_batch(["what time does the pool open"])

    results = await hybrid_search(db_session, query_text="pool open", query_vector=embedding.vector, guest_only=True)

    assert all(r.chunk.visibility == "guest" for r in results)
    assert any("infinity pool" in r.chunk.content_normalized.lower() for r in results)
    assert not any("staff-only" in r.chunk.content_normalized.lower() for r in results)


@pytest.mark.asyncio
async def test_hybrid_search_excludes_sources_not_yet_activated(db_session: AsyncSession):
    await _seeded_source(
        db_session, visibility="guest", text="Draft policy text not yet approved for guests.", activate=False
    )

    provider = MockEmbeddingProvider()
    [embedding] = await provider.embed_batch(["draft policy"])
    results = await hybrid_search(db_session, query_text="draft policy", query_vector=embedding.vector, guest_only=True)

    assert results == []


@pytest.mark.asyncio
async def test_hybrid_search_sparse_path_finds_exact_keyword_match(db_session: AsyncSession):
    await _seeded_source(
        db_session, visibility="guest",
        text="Airport transfers are available 24 hours with advance booking via the Transport Desk.",
    )

    provider = MockEmbeddingProvider()
    # Mock embeddings carry no real semantic signal, so a match here can
    # only come from the sparse (full-text) path — proving FTS is wired
    # up correctly, independent of dense similarity.
    [embedding] = await provider.embed_batch(["completely unrelated random query text"])
    results = await hybrid_search(
        db_session, query_text="airport transfers Transport Desk", query_vector=embedding.vector, guest_only=True
    )

    assert any("transport desk" in r.chunk.content_normalized.lower() for r in results)
    matching = next(r for r in results if "transport desk" in r.chunk.content_normalized.lower())
    assert matching.sparse_score > 0.0


@pytest.mark.asyncio
async def test_search_service_returns_citations_without_storage_paths(db_session: AsyncSession):
    await _seeded_source(db_session, visibility="guest", text="Check-in begins at 2:00 PM daily.")

    response = await retrieval_service.search(
        db_session,
        query_text="check-in time",
        embedding_provider=MockEmbeddingProvider(),
        reranker=HeuristicReranker(),
    )

    assert len(response.results) >= 1
    for citation in response.results:
        assert not hasattr(citation, "storage_path")
        assert citation.source_title == "Seed Source"

    log = await repository.get_retrieval_log(db_session, response.retrieval_log_id)
    assert log is not None
    assert log.query_text == "check-in time"
    assert log.result_count == len(response.results)
