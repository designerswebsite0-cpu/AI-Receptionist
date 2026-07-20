"""Settings hub (Phase X Stage 8) tests: Audit Logs read endpoint and
System Monitoring / Integrations status. Requires a reachable Postgres
(see conftest.db_engine); skips cleanly when none is available.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import repository as audit_repository
from app.audit.service import record_audit_event
from app.config import get_settings
from app.health import service as health_service
from app.users import repository as users_repository
from app.users.models import User


@pytest.mark.asyncio
async def test_list_audit_logs_filters_by_action(db_session: AsyncSession):
    await record_audit_event(
        db_session, actor_user_id=None, action="test.settings_hub_probe_a",
        resource_type="probe", resource_id="1",
    )
    await record_audit_event(
        db_session, actor_user_id=None, action="test.settings_hub_probe_b",
        resource_type="probe", resource_id="2",
    )
    await db_session.commit()

    logs, total = await audit_repository.list_audit_logs(db_session, action="test.settings_hub_probe_a")

    assert total == len(logs)
    assert all(log.action == "test.settings_hub_probe_a" for log in logs)


@pytest.mark.asyncio
async def test_list_audit_logs_search_matches_resource_type(db_session: AsyncSession):
    await record_audit_event(
        db_session, actor_user_id=None, action="test.settings_hub_search",
        resource_type="unique_probe_resource", resource_id="1",
    )
    await db_session.commit()

    logs, total = await audit_repository.list_audit_logs(db_session, search="unique_probe_resource")

    assert total >= 1
    assert any(log.resource_type == "unique_probe_resource" for log in logs)


@pytest.mark.asyncio
async def test_get_names_by_ids_resolves_full_name_or_email(db_session: AsyncSession):
    with_name = User(id=uuid.uuid4(), email="named@example.com", full_name="Named Staffer")
    without_name = User(id=uuid.uuid4(), email="unnamed@example.com")
    db_session.add_all([with_name, without_name])
    await db_session.commit()

    names = await users_repository.get_names_by_ids(db_session, [with_name.id, without_name.id])

    assert names[with_name.id] == "Named Staffer"
    assert names[without_name.id] == "unnamed@example.com"


def test_mask_key_shows_only_prefix_and_suffix():
    masked = health_service._mask("sk-abcdefghijklmnop")
    assert masked == "sk-a…mnop"
    assert "bcdefghijkl" not in masked


def test_mask_key_handles_none_and_short_values():
    assert health_service._mask(None) is None
    assert health_service._mask("short") == "•••••"


@pytest.mark.asyncio
async def test_get_system_status_reports_healthy_when_db_reachable(db_session: AsyncSession):
    status = await health_service.get_system_status(db_session)

    assert status["overall"] == "healthy"
    assert status["checks"]["database"] == "ok"


@pytest.mark.asyncio
async def test_get_integrations_status_never_exposes_raw_keys(db_session: AsyncSession):
    status = await health_service.get_integrations_status(db_session)

    settings = get_settings()
    if settings.openai_api_key:
        assert status["openai"]["masked_key"] != settings.openai_api_key
    assert "api_key" not in str(status)
