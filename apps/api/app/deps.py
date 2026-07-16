import uuid
from dataclasses import dataclass

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import VerifiedIdentity, verify_access_token
from app.database import get_db
from app.errors import ForbiddenError, UnauthorizedError
from app.logging import tenant_id_var, user_id_var
from app.tenants.models import TenantMember
from app.users.models import User
from app.users.service import upsert_user_from_identity


async def get_verified_identity(authorization: str | None = Header(default=None)) -> VerifiedIdentity:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("Missing or malformed Authorization header")
    token = authorization.split(" ", 1)[1]
    identity = verify_access_token(token)
    user_id_var.set(identity.user_id)
    return identity


async def get_current_user(
    identity: VerifiedIdentity = Depends(get_verified_identity),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the profile row for a verified identity.

    Login (app.auth.router.login) is expected to have already created this
    row via app.users.service.upsert_user_from_identity; the upsert here is
    a defense-in-depth fallback, not the primary creation path — it must
    not be the *only* place this happens, since several endpoints (e.g.
    audit logging during login itself) need the row to exist before this
    dependency is ever reached.
    """
    return await upsert_user_from_identity(db, identity)


@dataclass(frozen=True)
class CurrentMembership:
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    role_id: uuid.UUID
    role_name: str


async def get_current_membership(
    tenant_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CurrentMembership:
    """Resolve tenant context from a path-supplied tenant_id, but only ever
    trust it once it's been checked against the caller's own membership rows
    — this is the "verified source" rules.md §5/§6 requires, not a blind
    trust of client input.
    """
    from app.roles.models import TenantRole  # local import avoids a cycle with roles.permissions

    result = await db.execute(
        select(TenantMember, TenantRole.name)
        .join(TenantRole, TenantRole.id == TenantMember.role_id)
        .where(
            TenantMember.tenant_id == tenant_id,
            TenantMember.user_id == user.id,
            TenantMember.status == "active",
            TenantMember.deleted_at.is_(None),
        )
    )
    row = result.first()
    if row is None:
        raise ForbiddenError("You are not an active member of this tenant")
    member, role_name = row
    tenant_id_var.set(str(tenant_id))
    return CurrentMembership(tenant_id=tenant_id, user_id=user.id, role_id=member.role_id, role_name=role_name)
