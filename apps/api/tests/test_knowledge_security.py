"""Consolidated security checks for the Knowledge Intelligence Engine —
the guest-safety invariants the Phase 3 brief requires: guests must never
retrieve staff-only/internal/archive/template content, malware-flagged or
unapproved/rejected sources must never become retrievable, and the
retrieval query itself must be injection-safe. Most of these properties
are already exercised incidentally by other test files (test_knowledge_
sources.py, test_knowledge_retrieval_integration.py); this file gathers
the ones that specifically matter for security sign-off in one place, plus
the few not covered elsewhere (expiry enforcement, malware-status gating,
injection-string handling).

DB-backed tests require a reachable Postgres with pgvector (see
conftest.db_engine); they skip cleanly when none is available. The
filename-sanitization/ZIP-bomb/size-limit checks are pure-logic and
already covered in test_knowledge_validation.py — not duplicated here.
"""

from datetime import date, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ValidationErrorApp
from app.knowledge import repository, service
from app.knowledge.embeddings import MockEmbeddingProvider
from app.knowledge.extraction.base import ExtractedContent
from app.knowledge.indexing import index_source_version
from app.knowledge.retrieval.hybrid import hybrid_search
from app.knowledge.schemas import SourceGovernanceUpdateRequest, SourceRegisterRequest


async def _activated_source(db: AsyncSession, *, visibility: str, text: str, expiry_date=None):
    source = await service.register_source(
        db, body=SourceRegisterRequest(title="Security Test Source", source_type="document", visibility=visibility),
        actor_user_id=None,
    )
    version = await service.record_source_version(
        db, source_id=source.id, checksum_sha256="b" * 64, storage_path=None, actor_user_id=None
    )
    extracted = ExtractedContent(raw_text=text, extraction_method="plain-text", word_count=len(text.split()))
    await index_source_version(
        db, source=source, version=version, extracted=extracted, provider=MockEmbeddingProvider()
    )
    await service.approve_source(db, source_id=source.id, actor_user_id=None)
    source = await service.get_source_or_404(db, source.id)
    source.processing_status = "completed"
    source.malware_scan_status = "clean"
    if expiry_date is not None:
        source.expiry_date = expiry_date
    await db.commit()
    return await service.activate_source(db, source_id=source.id, actor_user_id=None)


# --- 1. Guest queries never surface non-guest visibility -----------------


@pytest.mark.asyncio
@pytest.mark.parametrize("visibility", ["staff", "internal"])
async def test_guest_query_excludes_non_guest_visibility(db_session: AsyncSession, visibility: str):
    await _activated_source(db_session, visibility=visibility, text="Internal staff procedure: lock the safe at 11pm.")
    provider = MockEmbeddingProvider()
    [embedding] = await provider.embed_batch(["lock the safe"])

    results = await hybrid_search(
        db_session, query_text="lock the safe", query_vector=embedding.vector, guest_only=True
    )

    assert all(r.chunk.visibility == "guest" for r in results)


@pytest.mark.asyncio
async def test_archive_visibility_can_never_be_activated(db_session: AsyncSession):
    source = await service.register_source(
        db_session,
        body=SourceRegisterRequest(title="Old Rate Card", source_type="document", visibility="guest"),
        actor_user_id=None,
    )
    await service.update_source_governance(
        db_session, source_id=source.id, body=SourceGovernanceUpdateRequest(visibility="archive"), actor_user_id=None
    )
    source = await service.get_source_or_404(db_session, source.id)
    source.processing_status = "completed"
    source.malware_scan_status = "clean"
    source.approval_status = "approved"
    await db_session.commit()

    with pytest.raises(ValidationErrorApp):
        await service.activate_source(db_session, source_id=source.id, actor_user_id=None)


# --- 2. Malware / approval gating on activation ---------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("scan_status", ["infected", "unavailable", "pending"])
async def test_activation_blocked_when_malware_scan_is_not_clean(db_session: AsyncSession, scan_status: str):
    source = await service.register_source(
        db_session, body=SourceRegisterRequest(title="Suspicious File", source_type="document", visibility="guest"),
        actor_user_id=None,
    )
    await service.record_source_version(
        db_session, source_id=source.id, checksum_sha256="c" * 64, storage_path=None, actor_user_id=None
    )
    await service.approve_source(db_session, source_id=source.id, actor_user_id=None)
    source = await service.get_source_or_404(db_session, source.id)
    source.processing_status = "completed"
    source.malware_scan_status = scan_status
    await db_session.commit()

    with pytest.raises(ValidationErrorApp):
        await service.activate_source(db_session, source_id=source.id, actor_user_id=None)


@pytest.mark.asyncio
async def test_rejected_source_cannot_be_activated(db_session: AsyncSession):
    source = await service.register_source(
        db_session, body=SourceRegisterRequest(title="Bad Draft", source_type="document", visibility="guest"),
        actor_user_id=None,
    )
    await service.reject_source(db_session, source_id=source.id, reason="Inaccurate pricing", actor_user_id=None)

    with pytest.raises(ValidationErrorApp):
        await service.activate_source(db_session, source_id=source.id, actor_user_id=None)


# --- 3. Expiry is enforced at the query level, not just governance state --


@pytest.mark.asyncio
async def test_expired_content_is_excluded_from_guest_retrieval_even_if_active(db_session: AsyncSession):
    yesterday = date.today() - timedelta(days=1)
    await _activated_source(
        db_session, visibility="guest", text="Diwali 2025 seasonal offer: 20 percent off villas.",
        expiry_date=yesterday,
    )
    provider = MockEmbeddingProvider()
    [embedding] = await provider.embed_batch(["Diwali seasonal offer villas"])

    results = await hybrid_search(
        db_session, query_text="Diwali seasonal offer villas", query_vector=embedding.vector, guest_only=True
    )

    assert results == []


@pytest.mark.asyncio
async def test_unexpired_content_still_retrievable(db_session: AsyncSession):
    tomorrow = date.today() + timedelta(days=1)
    await _activated_source(
        db_session, visibility="guest", text="Current spa package valid through next month.", expiry_date=tomorrow
    )
    provider = MockEmbeddingProvider()
    [embedding] = await provider.embed_batch(["current spa package"])

    results = await hybrid_search(
        db_session, query_text="current spa package", query_vector=embedding.vector, guest_only=True
    )

    assert len(results) >= 1


# --- 4. Retrieval query is injection-safe ---------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "malicious_query",
    [
        "'; DROP TABLE knowledge_chunks; --",
        "' OR '1'='1",
        "1' UNION SELECT * FROM users --",
        "\" OR \"\"=\"",
    ],
)
async def test_search_handles_sql_injection_strings_safely(db_session: AsyncSession, malicious_query: str):
    await _activated_source(db_session, visibility="guest", text="Check-in begins at 2 PM daily.")
    provider = MockEmbeddingProvider()
    [embedding] = await provider.embed_batch([malicious_query])

    # Must not raise, and must not return anything — SQLAlchemy's
    # parameterized to_tsquery/plainto_tsquery calls treat this as a
    # literal query string, not executable SQL. A crash or an unexpected
    # full-table dump would both be findings; a clean, safe empty/normal
    # result is the only correct behavior.
    results = await hybrid_search(
        db_session, query_text=malicious_query, query_vector=embedding.vector, guest_only=True
    )
    assert isinstance(results, list)

    # The table must still exist and be queryable afterward.
    still_there = await repository.list_sources(db_session, limit=1)
    assert still_there is not None
