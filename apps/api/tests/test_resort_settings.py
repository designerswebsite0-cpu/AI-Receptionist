"""resort_settings tests. Requires a reachable Postgres (see
conftest.db_engine); skips cleanly when none is available.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ConflictError, NotFoundError
from app.resort import service
from app.resort.schemas import ResortSettingsCreateRequest, ResortSettingsUpdateRequest


@pytest.mark.asyncio
async def test_create_resort_settings(db_session: AsyncSession):
    settings_row = await service.create_resort_settings(
        db_session, body=ResortSettingsCreateRequest(resort_name="Azure Bay Resort"), actor_user_id=None
    )
    assert settings_row.resort_name == "Azure Bay Resort"
    assert settings_row.timezone == "UTC"


@pytest.mark.asyncio
async def test_get_resort_settings_before_creation_is_not_found(db_session: AsyncSession):
    with pytest.raises(NotFoundError):
        await service.get_resort_settings_or_404(db_session)


@pytest.mark.asyncio
async def test_cannot_create_a_second_resort_settings_row(db_session: AsyncSession):
    await service.create_resort_settings(
        db_session, body=ResortSettingsCreateRequest(resort_name="First Resort"), actor_user_id=None
    )
    with pytest.raises(ConflictError):
        await service.create_resort_settings(
            db_session, body=ResortSettingsCreateRequest(resort_name="Second Resort"), actor_user_id=None
        )


@pytest.mark.asyncio
async def test_update_resort_settings_only_touches_provided_fields(db_session: AsyncSession):
    await service.create_resort_settings(
        db_session,
        body=ResortSettingsCreateRequest(resort_name="Azure Bay Resort", currency="USD"),
        actor_user_id=None,
    )

    updated = await service.update_resort_settings(
        db_session, body=ResortSettingsUpdateRequest(currency="INR"), actor_user_id=None
    )

    assert updated.resort_name == "Azure Bay Resort"
    assert updated.currency == "INR"
