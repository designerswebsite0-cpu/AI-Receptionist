"""Staff Management (Phase X Stage 4) tests. Requires a reachable Postgres
(see conftest.db_engine); skips cleanly when none is available.
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversations import repository as conversations_repository
from app.conversations.models import Conversation
from app.customers.schemas import CustomerCreateRequest
from app.customers.service import create_customer
from app.errors import NotFoundError
from app.users import repository, service
from app.users.models import User
from app.users.schemas import UserUpdateRequest


@pytest.mark.asyncio
async def test_new_user_defaults_to_active_administrator(db_session: AsyncSession):
    user = User(id=uuid.uuid4(), email="new-staff@example.com")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    assert user.role == "Administrator"
    assert user.status == "active"
    assert user.last_login_at is None


@pytest.mark.asyncio
async def test_update_user_only_touches_provided_fields(db_session: AsyncSession):
    user = User(id=uuid.uuid4(), email="staff-a@example.com", full_name="Original Name")
    db_session.add(user)
    await db_session.commit()

    updated = await service.update_user(
        db_session, user_id=user.id, body=UserUpdateRequest(status="inactive")
    )

    assert updated.full_name == "Original Name"
    assert updated.status == "inactive"


@pytest.mark.asyncio
async def test_get_nonexistent_user_returns_not_found(db_session: AsyncSession):
    with pytest.raises(NotFoundError):
        await service.get_user_or_404(db_session, uuid.uuid4())


@pytest.mark.asyncio
async def test_list_users_filters_by_status_and_search(db_session: AsyncSession):
    active = User(id=uuid.uuid4(), email="active-staff@example.com", full_name="Alice Active")
    inactive = User(id=uuid.uuid4(), email="inactive-staff@example.com", full_name="Ivy Inactive", status="inactive")
    db_session.add_all([active, inactive])
    await db_session.commit()

    active_only, total_active = await repository.list_users(db_session, status="active")
    assert total_active >= 1
    assert all(u.status == "active" for u in active_only)

    by_search, total_search = await repository.list_users(db_session, search="Ivy")
    assert total_search == 1
    assert by_search[0].email == "inactive-staff@example.com"


@pytest.mark.asyncio
async def test_count_open_conversations_by_agent_excludes_closed(db_session: AsyncSession):
    agent = User(id=uuid.uuid4(), email="agent@example.com")
    db_session.add(agent)
    customer = await create_customer(db_session, body=CustomerCreateRequest(), actor_user_id=None)

    open_convo = Conversation(
        customer_id=customer.id, channel="webchat", status="open",
        assigned_agent_id=agent.id, started_at=datetime.now(UTC),
    )
    closed_convo = Conversation(
        customer_id=customer.id, channel="webchat", status="closed",
        assigned_agent_id=agent.id, started_at=datetime.now(UTC),
    )
    db_session.add_all([open_convo, closed_convo])
    await db_session.commit()

    counts = await conversations_repository.count_open_conversations_by_agent(db_session, [agent.id])
    assert counts[agent.id] == 1
