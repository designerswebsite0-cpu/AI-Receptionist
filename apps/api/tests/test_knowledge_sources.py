"""Phase 3 core domain: knowledge source lifecycle. Requires a reachable
Postgres with pgvector (see conftest.db_engine); skips cleanly when none
is available. Full retrieval/ingestion-pipeline coverage lands with the
later Phase 3 steps (chunking, embeddings, malware scanning) — this file
only exercises the governance state machine in app.knowledge.service.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ConflictError, NotFoundError, ValidationErrorApp
from app.knowledge import service
from app.knowledge.schemas import SourceGovernanceUpdateRequest, SourceRegisterRequest


def _register_request(**overrides) -> SourceRegisterRequest:
    defaults = dict(
        source_id=None,
        title="Deluxe Suite Rate Card",
        source_type="document",
        visibility="guest",
    )
    defaults.update(overrides)
    return SourceRegisterRequest(**defaults)


@pytest.mark.asyncio
async def test_register_source_defaults_to_pending_and_not_retrievable(db_session: AsyncSession):
    source = await service.register_source(db_session, body=_register_request(), actor_user_id=None)

    assert source.status == "draft"
    assert source.approval_status == "pending"
    assert source.processing_status == "pending"
    assert source.retrieval_enabled is False


@pytest.mark.asyncio
async def test_duplicate_external_source_id_is_rejected(db_session: AsyncSession):
    await service.register_source(db_session, body=_register_request(source_id="SRC-001"), actor_user_id=None)

    with pytest.raises(ConflictError):
        await service.register_source(
            db_session, body=_register_request(source_id="SRC-001", title="Different title"), actor_user_id=None
        )


@pytest.mark.asyncio
async def test_activation_blocked_before_approval(db_session: AsyncSession):
    source = await service.register_source(db_session, body=_register_request(), actor_user_id=None)

    with pytest.raises(ValidationErrorApp):
        await service.activate_source(db_session, source_id=source.id, actor_user_id=None)


@pytest.mark.asyncio
async def test_activation_blocked_before_processing_completes(db_session: AsyncSession):
    source = await service.register_source(db_session, body=_register_request(), actor_user_id=None)
    await service.approve_source(db_session, source_id=source.id, actor_user_id=None)

    # processing_status is still "pending" — no version has been recorded.
    with pytest.raises(ValidationErrorApp):
        await service.activate_source(db_session, source_id=source.id, actor_user_id=None)


@pytest.mark.asyncio
async def test_full_lifecycle_reaches_retrieval_enabled(db_session: AsyncSession):
    source = await service.register_source(db_session, body=_register_request(), actor_user_id=None)
    await service.record_source_version(
        db_session, source_id=source.id, checksum_sha256="a" * 64, storage_path="sources/rate-card.pdf",
        actor_user_id=None,
    )
    await service.approve_source(db_session, source_id=source.id, actor_user_id=None)

    source = await service.get_source_or_404(db_session, source.id)
    source.processing_status = "completed"
    source.malware_scan_status = "clean"
    await db_session.commit()

    activated = await service.activate_source(db_session, source_id=source.id, actor_user_id=None)

    assert activated.status == "active"
    assert activated.retrieval_enabled is True


@pytest.mark.asyncio
async def test_archive_source_revokes_retrieval(db_session: AsyncSession):
    source = await service.register_source(db_session, body=_register_request(), actor_user_id=None)
    await service.record_source_version(
        db_session, source_id=source.id, checksum_sha256="b" * 64, storage_path=None, actor_user_id=None
    )
    await service.approve_source(db_session, source_id=source.id, actor_user_id=None)
    source = await service.get_source_or_404(db_session, source.id)
    source.processing_status = "completed"
    source.malware_scan_status = "clean"
    await db_session.commit()
    await service.activate_source(db_session, source_id=source.id, actor_user_id=None)

    archived = await service.archive_source(db_session, source_id=source.id, actor_user_id=None)

    assert archived.status == "archived"
    assert archived.retrieval_enabled is False


@pytest.mark.asyncio
async def test_governance_update_to_archive_visibility_revokes_retrieval(db_session: AsyncSession):
    source = await service.register_source(db_session, body=_register_request(), actor_user_id=None)
    await service.record_source_version(
        db_session, source_id=source.id, checksum_sha256="e" * 64, storage_path=None, actor_user_id=None
    )
    await service.approve_source(db_session, source_id=source.id, actor_user_id=None)
    source = await service.get_source_or_404(db_session, source.id)
    source.processing_status = "completed"
    source.malware_scan_status = "clean"
    await db_session.commit()
    activated = await service.activate_source(db_session, source_id=source.id, actor_user_id=None)
    assert activated.retrieval_enabled is True

    updated = await service.update_source_governance(
        db_session,
        source_id=source.id,
        body=SourceGovernanceUpdateRequest(visibility="archive"),
        actor_user_id=None,
    )

    assert updated.visibility == "archive"
    assert updated.retrieval_enabled is False


@pytest.mark.asyncio
async def test_get_nonexistent_source_raises_not_found(db_session: AsyncSession):
    with pytest.raises(NotFoundError):
        await service.get_source_or_404(db_session, uuid.uuid4())


@pytest.mark.asyncio
async def test_version_numbers_increment_and_track_current(db_session: AsyncSession):
    source = await service.register_source(db_session, body=_register_request(), actor_user_id=None)

    v1 = await service.record_source_version(
        db_session, source_id=source.id, checksum_sha256="c" * 64, storage_path=None, actor_user_id=None
    )
    v2 = await service.record_source_version(
        db_session, source_id=source.id, checksum_sha256="d" * 64, storage_path=None, actor_user_id=None
    )

    assert v1.version_number == 1
    assert v2.version_number == 2
    assert v2.is_current is True

    refreshed_v1 = await service.get_source_or_404(db_session, source.id)
    assert refreshed_v1.current_version_id == v2.id
