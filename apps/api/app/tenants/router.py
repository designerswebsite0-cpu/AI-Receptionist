import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import success
from app.database import get_db
from app.deps import CurrentMembership, get_current_user
from app.roles.permissions import Permission, require_permission
from app.tenants import service
from app.tenants.schemas import (
    MemberInviteRequest,
    MemberRoleUpdateRequest,
    TenantCreateRequest,
)
from app.users.models import User

router = APIRouter(prefix="/api/v1/tenants", tags=["tenants"])


@router.post("")
async def create_tenant(
    body: TenantCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    tenant = await service.create_tenant(db, name=body.name, slug=body.slug, owner=user)
    return success(
        {"id": str(tenant.id), "name": tenant.name, "slug": tenant.slug, "status": tenant.status}
    )


@router.get("/me")
async def list_my_tenants(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    memberships = await service.list_my_tenants(db, user.id)
    return success(
        [
            {**m, "tenant_id": str(m["tenant_id"])}
            for m in memberships
        ]
    )


@router.get("/{tenant_id}")
async def get_tenant(
    tenant_id: uuid.UUID,
    membership: CurrentMembership = Depends(require_permission(Permission.TENANT_VIEW)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    tenant = await service.get_tenant_or_404(db, tenant_id)
    return success(
        {"id": str(tenant.id), "name": tenant.name, "slug": tenant.slug, "status": tenant.status}
    )


@router.get("/{tenant_id}/members")
async def list_members(
    tenant_id: uuid.UUID,
    membership: CurrentMembership = Depends(require_permission(Permission.MEMBERS_VIEW)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    members = await service.list_members(db, tenant_id)
    return success(
        [{**m, "id": str(m["id"]), "user_id": str(m["user_id"])} for m in members]
    )


@router.post("/{tenant_id}/members")
async def invite_member(
    tenant_id: uuid.UUID,
    body: MemberInviteRequest,
    membership: CurrentMembership = Depends(require_permission(Permission.MEMBERS_INVITE)),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    member = await service.invite_member(db, tenant_id=tenant_id, email=body.email, role=body.role, actor=user)
    return success({**member, "id": str(member["id"]), "user_id": str(member["user_id"])})


@router.patch("/{tenant_id}/members/{member_id}")
async def update_member_role(
    tenant_id: uuid.UUID,
    member_id: uuid.UUID,
    body: MemberRoleUpdateRequest,
    membership: CurrentMembership = Depends(require_permission(Permission.MEMBERS_UPDATE_ROLE)),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    member = await service.update_member_role(
        db, tenant_id=tenant_id, member_id=member_id, new_role=body.role, actor=user
    )
    return success({"id": str(member.id), "status": member.status})


@router.delete("/{tenant_id}/members/{member_id}")
async def remove_member(
    tenant_id: uuid.UUID,
    member_id: uuid.UUID,
    membership: CurrentMembership = Depends(require_permission(Permission.MEMBERS_REMOVE)),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await service.remove_member(db, tenant_id=tenant_id, member_id=member_id, actor=user)
    return success({"removed": True})
