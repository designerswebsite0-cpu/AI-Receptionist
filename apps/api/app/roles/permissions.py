from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_membership
from app.errors import ForbiddenError
from app.roles.models import TenantPermission
from app.roles.seed_data import ALL_PERMISSIONS, SYSTEM_ROLES, Permission

__all__ = ["ALL_PERMISSIONS", "SYSTEM_ROLES", "Permission", "require_permission"]


def require_permission(permission_key: str):
    """FastAPI dependency factory: 403s unless the current membership's role
    has been granted `permission_key`. Depends on `get_current_membership`
    from app.deps, which itself only accepts a tenant_id already verified
    against the caller's own memberships — never a raw client-supplied value.

    Temporary development-phase behavior (docs/product_decisions.md): while
    `settings.rbac_enforcement_enabled` is False, the permission check itself
    is skipped and any active tenant member passes. `get_current_membership`
    still runs first, so tenant isolation is never affected by this flag —
    only role-granularity is relaxed. The role/permission tables and this
    check remain fully intact so enforcement can be flipped back on later
    without touching callers.
    """

    async def _dependency(
        membership=Depends(get_current_membership),
        db: AsyncSession = Depends(get_db),
    ):
        if not get_settings().rbac_enforcement_enabled:
            return membership

        result = await db.execute(
            select(TenantPermission.permission_key).where(TenantPermission.role_id == membership.role_id)
        )
        granted = {row[0] for row in result.all()}
        if permission_key not in granted:
            raise ForbiddenError(f"Missing required permission: {permission_key}")
        return membership

    return _dependency
