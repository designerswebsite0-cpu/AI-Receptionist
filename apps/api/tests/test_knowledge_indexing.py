"""Integration tests for app.knowledge.indexing — requires a reachable
Postgres with pgvector (see conftest.db_engine); skips cleanly when none
is available. Uses MockEmbeddingProvider throughout, per the Phase 3
brief's testing rules (no external paid API calls in normal test runs).
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge import repository, service
from app.knowledge.embeddings import MockEmbeddingProvider
from app.knowledge.extraction.base import ExtractedContent
from app.knowledge.indexing import index_source_version
from app.knowledge.schemas import SourceRegisterRequest


async def _make_source_and_version(db: AsyncSession, *, visibility: str = "guest"):
    source = await service.register_source(
        db,
        body=SourceRegisterRequest(title="Test FAQ", source_type="document", visibility=visibility),
        actor_user_id=None,
    )
    version = await service.record_source_version(
        db, source_id=source.id, checksum_sha256="f" * 64, storage_path=None, actor_user_id=None
    )
    return source, version


@pytest.mark.asyncio
async def test_index_source_version_creates_chunks_with_embeddings(db_session: AsyncSession):
    source, version = await _make_source_and_version(db_session)
    extracted = ExtractedContent(
        raw_text=(
            "Q: What time is check-in? A: 2 PM.\n\n"
            "Q: What time is check-out? A: 11 AM.\n\n"
            "Q: Is Wi-Fi free? A: Yes."
        ),
        extraction_method="plain-text",
        word_count=20,
    )
    provider = MockEmbeddingProvider()

    result = await index_source_version(
        db_session, source=source, version=version, extracted=extracted, provider=provider
    )
    await db_session.commit()

    assert result.chunks_created == 3
    assert result.chunks_embedded == 3

    chunks = await repository.list_chunks_for_source(db_session, source.id)
    assert len(chunks) == 3
    assert all(chunk.embedding is not None for chunk in chunks)
    assert all(chunk.visibility == "guest" for chunk in chunks)


@pytest.mark.asyncio
async def test_index_source_version_is_idempotent_for_unchanged_content(db_session: AsyncSession):
    source, version = await _make_source_and_version(db_session)
    extracted = ExtractedContent(
        raw_text="Q: Is parking available? A: Yes, complimentary parking.\n\n"
        "Q: Are pets allowed? A: No, except service animals.\n\n"
        "Q: Is smoking allowed? A: No, designated areas only.",
        extraction_method="plain-text",
        word_count=15,
    )
    provider = MockEmbeddingProvider()

    first = await index_source_version(
        db_session, source=source, version=version, extracted=extracted, provider=provider
    )
    await db_session.commit()
    second = await index_source_version(
        db_session, source=source, version=version, extracted=extracted, provider=provider
    )
    await db_session.commit()

    assert first.chunks_created == 3
    assert second.chunks_created == 0
    assert second.chunks_updated == 3
    assert second.chunks_embedded == 0  # unchanged content, same model — nothing re-embedded

    chunks = await repository.list_chunks_for_source(db_session, source.id)
    assert len(chunks) == 3  # no duplicates from the second run


@pytest.mark.asyncio
async def test_index_source_version_removes_stale_chunks_when_content_shrinks(db_session: AsyncSession):
    source, version = await _make_source_and_version(db_session)
    provider = MockEmbeddingProvider()

    big = ExtractedContent(
        raw_text="Q: One? A: First.\n\nQ: Two? A: Second.\n\nQ: Three? A: Third.",
        extraction_method="plain-text",
        word_count=10,
    )
    await index_source_version(db_session, source=source, version=version, extracted=big, provider=provider)
    await db_session.commit()

    small = ExtractedContent(
        raw_text="Q: One? A: First.\n\nQ: Two? A: Second.", extraction_method="plain-text", word_count=6
    )
    result = await index_source_version(db_session, source=source, version=version, extracted=small, provider=provider)
    await db_session.commit()

    assert result.chunks_deleted == 1
    chunks = await repository.list_chunks_for_source(db_session, source.id)
    assert len(chunks) == 2


@pytest.mark.asyncio
async def test_index_source_version_denormalizes_governance_from_source(db_session: AsyncSession):
    source, version = await _make_source_and_version(db_session, visibility="staff")
    source.authoritative = True
    extracted = ExtractedContent(
        raw_text="Internal procedure text goes here.", extraction_method="plain-text", word_count=5
    )
    provider = MockEmbeddingProvider()

    await index_source_version(
        db_session, source=source, version=version, extracted=extracted, provider=provider
    )
    await db_session.commit()

    chunks = await repository.list_chunks_for_source(db_session, source.id)
    assert len(chunks) == 1
    assert chunks[0].visibility == "staff"
    assert chunks[0].authoritative is True
    assert chunks[0].retrieval_enabled is False  # source was never activated
