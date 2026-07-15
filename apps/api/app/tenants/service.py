import uuid
from datetime import UTC

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_audit_event
from app.errors import ConflictError, NotFoundError, ValidationErrorApp
from app.roles.permissions import SYSTEM_ROLES
from app.tenants import repository
from app.tenants.models import Tenant, TenantMember
from app.users.models import User


async def create_tenant(db: AsyncSession, *, name: str, slug: str, owner: User) -> Tenant:
    if await repository.get_tenant_by_slug(db, slug) is not None:
        raise ConflictError(f"Tenant slug '{slug}' is already taken")

    owner_role = await repository.get_system_role_by_name(db, "owner")
    if owner_role is None:
        raise RuntimeError("System role 'owner' is not seeded — run migrations")

    tenant = repository.new_tenant(name=name, slug=slug)
    db.add(tenant)
    await db.flush()  # populate tenant.id before FK references

    db.add(repository.new_tenant_settings(tenant.id))
    db.add(repository.new_member(tenant.id, owner.id, owner_role.id))

    await record_audit_event(
        db,
        tenant_id=tenant.id,
        actor_user_id=owner.id,
        action="tenant.created",
        resource_type="tenant",
        resource_id=str(tenant.id),
        metadata={"name": name, "slug": slug},
    )
    await db.commit()
    await db.refresh(tenant)
    return tenant


async def list_my_tenants(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    rows = await repository.list_memberships_for_user(db, user_id)
    return [
        {"tenant_id": tenant.id, "tenant_name": tenant.name, "tenant_slug": tenant.slug, "role": role_name}
        for _member, tenant, role_name in rows
    ]


async def get_tenant_or_404(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant:
    tenant = await repository.get_tenant(db, tenant_id)
    if tenant is None:
        raise NotFoundError("Tenant not found")
    return tenant


async def list_members(db: AsyncSession, tenant_id: uuid.UUID) -> list[dict]:
    rows = await repository.list_members(db, tenant_id)
    return [
        {
            "id": member.id,
            "user_id": user.id,
            "email": user.email,
            "role": role_name,
            "status": member.status,
            "joined_at": member.joined_at,
        }
        for member, user, role_name in rows
    ]


async def invite_member(
    db: AsyncSession, *, tenant_id: uuid.UUID, email: str, role: str, actor: User
) -> dict:
    if role not in SYSTEM_ROLES:
        raise ValidationErrorApp(f"Unknown role '{role}'")

    invitee = await repository.get_user_by_email(db, email)
    if invitee is None:
        # Phase 1 simplification: invites require the person to already have
        # signed up via Supabase Auth. A pending-invite-by-email flow (with
        # its own table + emailed accept link) is documented follow-up work
        # once Resend is wired in Phase 7 — not a silent gap.
        raise NotFoundError(
            "No account found for that email yet — ask them to sign up first, then invite again"
        )

    if await repository.get_member_by_user(db, tenant_id, invitee.id) is not None:
        raise ConflictError("This user is already a member of the tenant")

    role_row = await repository.get_system_role_by_name(db, role)
    if role_row is None:
        raise RuntimeError(f"System role '{role}' is not seeded — run migrations")

    member = repository.new_member(tenant_id, invitee.id, role_row.id, invited_by=actor.id)
    db.add(member)
    await db.flush()

    await record_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor.id,
        action="member.invited",
        resource_type="tenant_member",
        resource_id=str(member.id),
        metadata={"invited_email": email, "role": role},
    )
    await db.commit()
    return {
        "id": member.id,
        "user_id": invitee.id,
        "email": invitee.email,
        "role": role,
        "status": member.status,
        "joined_at": member.joined_at,
    }


async def update_member_role(
    db: AsyncSession, *, tenant_id: uuid.UUID, member_id: uuid.UUID, new_role: str, actor: User
) -> TenantMember:
    if new_role not in SYSTEM_ROLES:
        raise ValidationErrorApp(f"Unknown role '{new_role}'")

    member = await repository.get_member_by_id(db, tenant_id, member_id)
    if member is None:
        raise NotFoundError("Member not found")

    await _guard_last_owner(db, tenant_id, member, new_role_name=new_role)

    role_row = await repository.get_system_role_by_name(db, new_role)
    if role_row is None:
        raise RuntimeError(f"System role '{new_role}' is not seeded — run migrations")

    old_role_id = member.role_id
    member.role_id = role_row.id

    await record_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor.id,
        action="member.role_updated",
        resource_type="tenant_member",
        resource_id=str(member.id),
        metadata={"old_role_id": str(old_role_id), "new_role": new_role},
    )
    await db.commit()
    await db.refresh(member)
    return member


async def remove_member(db: AsyncSession, *, tenant_id: uuid.UUID, member_id: uuid.UUID, actor: User) -> None:
    from datetime import datetime

    member = await repository.get_member_by_id(db, tenant_id, member_id)
    if member is None:
        raise NotFoundError("Member not found")

    await _guard_last_owner(db, tenant_id, member, new_role_name=None)

    member.status = "removed"
    member.deleted_at = datetime.now(UTC)

    await record_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor.id,
        action="member.removed",
        resource_type="tenant_member",
        resource_id=str(member.id),
        metadata={},
    )
    await db.commit()


async def _guard_last_owner(
    db: AsyncSession, tenant_id: uuid.UUID, member: TenantMember, *, new_role_name: str | None
) -> None:
    """Prevent removing/demoting the tenant's last remaining owner."""
    role_row = await repository.get_system_role_by_name(db, "owner")
    if role_row is None or member.role_id != role_row.id:
        return
    if new_role_name == "owner":
        return

    rows = await repository.list_members(db, tenant_id)
    owners_remaining = [m for m, _user, role_name in rows if role_name == "owner" and m.status == "active"]
    if len(owners_remaining) <= 1:
        raise ConflictError("Cannot remove or demote the last remaining owner of a tenant")
