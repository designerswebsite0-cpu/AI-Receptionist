import uuid
from datetime import UTC

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.roles.models import TenantRole
from app.tenants.models import Tenant, TenantMember, TenantSettings
from app.users.models import User


async def get_tenant_by_slug(db: AsyncSession, slug: str) -> Tenant | None:
    result = await db.execute(select(Tenant).where(Tenant.slug == slug, Tenant.deleted_at.is_(None)))
    return result.scalar_one_or_none()


async def get_tenant(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant | None:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id, Tenant.deleted_at.is_(None)))
    return result.scalar_one_or_none()


async def get_system_role_by_name(db: AsyncSession, name: str) -> TenantRole | None:
    result = await db.execute(
        select(TenantRole).where(TenantRole.name == name, TenantRole.tenant_id.is_(None))
    )
    return result.scalar_one_or_none()


async def list_memberships_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[tuple[TenantMember, Tenant, str]]:
    result = await db.execute(
        select(TenantMember, Tenant, TenantRole.name)
        .join(Tenant, Tenant.id == TenantMember.tenant_id)
        .join(TenantRole, TenantRole.id == TenantMember.role_id)
        .where(
            TenantMember.user_id == user_id,
            TenantMember.status == "active",
            TenantMember.deleted_at.is_(None),
            Tenant.deleted_at.is_(None),
        )
    )
    return list(result.all())


async def get_member_by_id(db: AsyncSession, tenant_id: uuid.UUID, member_id: uuid.UUID) -> TenantMember | None:
    result = await db.execute(
        select(TenantMember).where(
            TenantMember.id == member_id,
            TenantMember.tenant_id == tenant_id,
            TenantMember.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def get_member_by_user(db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID) -> TenantMember | None:
    result = await db.execute(
        select(TenantMember).where(
            TenantMember.tenant_id == tenant_id,
            TenantMember.user_id == user_id,
            TenantMember.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def list_members(db: AsyncSession, tenant_id: uuid.UUID) -> list[tuple[TenantMember, User, str]]:
    result = await db.execute(
        select(TenantMember, User, TenantRole.name)
        .join(User, User.id == TenantMember.user_id)
        .join(TenantRole, TenantRole.id == TenantMember.role_id)
        .where(TenantMember.tenant_id == tenant_id, TenantMember.deleted_at.is_(None))
        .order_by(TenantMember.created_at)
    )
    return list(result.all())


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


def new_tenant(name: str, slug: str) -> Tenant:
    return Tenant(name=name, slug=slug, status="active")


def new_tenant_settings(tenant_id: uuid.UUID) -> TenantSettings:
    return TenantSettings(tenant_id=tenant_id)


def new_member(tenant_id: uuid.UUID, user_id: uuid.UUID, role_id: uuid.UUID, *, invited_by: uuid.UUID | None = None):
    from datetime import datetime

    return TenantMember(
        tenant_id=tenant_id,
        user_id=user_id,
        role_id=role_id,
        status="active",
        invited_by=invited_by,
        joined_at=datetime.now(UTC),
    )
