"""Cross-tenant isolation tests — release-blocking per architecture.md §6.

Requires a reachable Postgres (see conftest.db_engine); skips cleanly when
none is available, e.g. no Docker/Supabase configured on this machine.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_membership
from app.errors import ForbiddenError
from app.roles.models import TenantPermission, TenantRole
from app.roles.seed_data import SYSTEM_ROLES
from app.tenants.models import Tenant, TenantMember
from app.users.models import User


async def _seed_roles(db: AsyncSession) -> dict[str, TenantRole]:
    roles: dict[str, TenantRole] = {}
    for name, perms in SYSTEM_ROLES.items():
        role = TenantRole(tenant_id=None, name=name, is_system=True)
        db.add(role)
        await db.flush()
        for perm in perms:
            db.add(TenantPermission(role_id=role.id, permission_key=perm))
        roles[name] = role
    await db.commit()
    return roles


@pytest.mark.asyncio
async def test_user_cannot_resolve_membership_in_a_tenant_they_do_not_belong_to(db_session: AsyncSession):
    roles = await _seed_roles(db_session)

    tenant_a = Tenant(name="Tenant A", slug="tenant-a")
    tenant_b = Tenant(name="Tenant B", slug="tenant-b")
    db_session.add_all([tenant_a, tenant_b])
    await db_session.flush()

    user = User(id=uuid.uuid4(), email="member-of-a@example.com")
    db_session.add(user)
    await db_session.flush()

    db_session.add(TenantMember(tenant_id=tenant_a.id, user_id=user.id, role_id=roles["staff"].id, status="active"))
    await db_session.commit()

    # Belongs to A: resolves fine.
    membership = await get_current_membership(tenant_id=tenant_a.id, user=user, db=db_session)
    assert membership.tenant_id == tenant_a.id
    assert membership.role_name == "staff"

    # Does not belong to B: must be rejected, not silently scoped to A.
    with pytest.raises(ForbiddenError):
        await get_current_membership(tenant_id=tenant_b.id, user=user, db=db_session)


@pytest.mark.asyncio
async def test_list_members_never_returns_another_tenants_members(db_session: AsyncSession):
    from app.tenants import repository

    roles = await _seed_roles(db_session)

    tenant_a = Tenant(name="Tenant A", slug="tenant-a-2")
    tenant_b = Tenant(name="Tenant B", slug="tenant-b-2")
    db_session.add_all([tenant_a, tenant_b])
    await db_session.flush()

    user_a = User(id=uuid.uuid4(), email="a@example.com")
    user_b = User(id=uuid.uuid4(), email="b@example.com")
    db_session.add_all([user_a, user_b])
    await db_session.flush()

    db_session.add(TenantMember(tenant_id=tenant_a.id, user_id=user_a.id, role_id=roles["owner"].id, status="active"))
    db_session.add(TenantMember(tenant_id=tenant_b.id, user_id=user_b.id, role_id=roles["owner"].id, status="active"))
    await db_session.commit()

    members_of_a = await repository.list_members(db_session, tenant_a.id)
    assert len(members_of_a) == 1
    assert members_of_a[0][1].id == user_a.id
