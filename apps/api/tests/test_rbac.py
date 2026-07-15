import uuid

import pytest

from app.config import get_settings
from app.roles import permissions as permissions_module
from app.roles.permissions import ALL_PERMISSIONS, SYSTEM_ROLES, Permission, require_permission


def test_five_system_roles_are_seeded():
    assert set(SYSTEM_ROLES.keys()) == {"owner", "admin", "manager", "staff", "read_only"}


def test_owner_and_admin_have_every_permission():
    assert set(SYSTEM_ROLES["owner"]) == set(ALL_PERMISSIONS)
    assert set(SYSTEM_ROLES["admin"]) == set(ALL_PERMISSIONS)


def test_read_only_cannot_invite_or_manage_members():
    read_only_perms = set(SYSTEM_ROLES["read_only"])
    assert Permission.MEMBERS_INVITE not in read_only_perms
    assert Permission.MEMBERS_REMOVE not in read_only_perms
    assert Permission.TENANT_MANAGE_SETTINGS not in read_only_perms


def test_staff_cannot_manage_tenant_settings():
    assert Permission.TENANT_MANAGE_SETTINGS not in set(SYSTEM_ROLES["staff"])


def test_every_role_can_at_least_view_the_tenant():
    for role, perms in SYSTEM_ROLES.items():
        assert Permission.TENANT_VIEW in perms, f"{role} cannot even view its own tenant"


class _FakeMembership:
    def __init__(self, role_id: uuid.UUID) -> None:
        self.role_id = role_id
        self.tenant_id = uuid.uuid4()
        self.user_id = uuid.uuid4()
        self.role_name = "read_only"


@pytest.mark.asyncio
async def test_permission_check_is_bypassed_by_default_in_dev_phase():
    """Temporary dev-phase behavior (docs/product_decisions.md): with
    RBAC_ENFORCEMENT_ENABLED=false (the default), any resolved membership
    passes require_permission() without a permissions lookup at all — the
    `db=None` here proves no query is attempted.
    """
    assert get_settings().rbac_enforcement_enabled is False

    dependency = require_permission(Permission.TENANT_MANAGE_SETTINGS)
    membership = _FakeMembership(role_id=uuid.uuid4())  # role has zero permissions rows

    result = await dependency(membership=membership, db=None)
    assert result is membership


@pytest.mark.asyncio
async def test_permission_check_still_enforces_when_flag_is_enabled(monkeypatch, db_session):
    """Proves the bypass is a real toggle, not a deleted check: flipping
    the flag back on must still reject a role lacking the permission.
    """
    from app.roles.models import TenantPermission, TenantRole

    role = TenantRole(tenant_id=None, name="read_only_test", is_system=True)
    db_session.add(role)
    await db_session.flush()
    db_session.add(TenantPermission(role_id=role.id, permission_key=Permission.TENANT_VIEW))
    await db_session.commit()

    class _EnforcingSettings:
        rbac_enforcement_enabled = True

    monkeypatch.setattr(permissions_module, "get_settings", lambda: _EnforcingSettings())

    dependency = require_permission(Permission.TENANT_MANAGE_SETTINGS)
    membership = _FakeMembership(role_id=role.id)

    from app.errors import ForbiddenError

    with pytest.raises(ForbiddenError):
        await dependency(membership=membership, db=db_session)
