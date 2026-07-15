import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import PageParams, build_page_meta
from app.common.responses import success
from app.customers import repository, service
from app.customers.schemas import (
    ContactIn,
    CustomerCreateRequest,
    CustomerOut,
    CustomerUpdateRequest,
    NoteCreateRequest,
    TagCreateRequest,
)
from app.database import get_db
from app.deps import CurrentMembership
from app.roles.permissions import Permission, require_permission

router = APIRouter(prefix="/api/v1/tenants/{tenant_id}/customers", tags=["customers"])


@router.post("")
async def create_customer(
    tenant_id: uuid.UUID,
    body: CustomerCreateRequest,
    membership: CurrentMembership = Depends(require_permission(Permission.CUSTOMERS_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    customer = await service.create_customer(
        db, tenant_id=tenant_id, body=body, actor_user_id=membership.user_id
    )
    return success(CustomerOut.model_validate(customer).model_dump(mode="json"))


@router.get("")
async def list_customers(
    tenant_id: uuid.UUID,
    search: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    membership: CurrentMembership = Depends(require_permission(Permission.CUSTOMERS_VIEW)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    params = PageParams(page=page, page_size=page_size)
    customers, total = await repository.search_customers(
        db, tenant_id, search=search, tag=tag, offset=params.offset, limit=params.page_size
    )
    return success(
        {
            "items": [CustomerOut.model_validate(c).model_dump(mode="json") for c in customers],
            "meta": build_page_meta(params, total).model_dump(),
        }
    )


@router.get("/{customer_id}")
async def get_customer(
    tenant_id: uuid.UUID,
    customer_id: uuid.UUID,
    membership: CurrentMembership = Depends(require_permission(Permission.CUSTOMERS_VIEW)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    customer = await service.get_customer_or_404(db, tenant_id, customer_id)
    contacts = await repository.list_contacts(db, tenant_id, customer_id)
    tags = await repository.list_tags(db, tenant_id, customer_id)
    payload = CustomerOut.model_validate(customer).model_dump(mode="json")
    payload["contacts"] = [
        {
            "id": str(c.id),
            "contact_type": c.contact_type,
            "value": c.value,
            "is_primary": c.is_primary,
            "verified": c.verified,
        }
        for c in contacts
    ]
    payload["tags"] = [t.tag for t in tags]
    return success(payload)


@router.patch("/{customer_id}")
async def update_customer(
    tenant_id: uuid.UUID,
    customer_id: uuid.UUID,
    body: CustomerUpdateRequest,
    membership: CurrentMembership = Depends(require_permission(Permission.CUSTOMERS_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    customer = await service.update_customer(
        db, tenant_id=tenant_id, customer_id=customer_id, body=body, actor_user_id=membership.user_id
    )
    return success(CustomerOut.model_validate(customer).model_dump(mode="json"))


@router.post("/{customer_id}/contacts")
async def add_contact(
    tenant_id: uuid.UUID,
    customer_id: uuid.UUID,
    body: ContactIn,
    membership: CurrentMembership = Depends(require_permission(Permission.CUSTOMERS_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    contact = await service.add_contact(
        db, tenant_id=tenant_id, customer_id=customer_id, body=body, actor_user_id=membership.user_id
    )
    return success(
        {
            "id": str(contact.id),
            "contact_type": contact.contact_type,
            "value": contact.value,
            "is_primary": contact.is_primary,
            "verified": contact.verified,
        }
    )


@router.get("/{customer_id}/notes")
async def list_notes(
    tenant_id: uuid.UUID,
    customer_id: uuid.UUID,
    membership: CurrentMembership = Depends(require_permission(Permission.CUSTOMERS_VIEW)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    notes = await repository.list_notes(db, tenant_id, customer_id)
    return success(
        [
            {
                "id": str(n.id),
                "author_user_id": str(n.author_user_id) if n.author_user_id else None,
                "note": n.note,
                "created_at": n.created_at.isoformat(),
            }
            for n in notes
        ]
    )


@router.post("/{customer_id}/notes")
async def add_note(
    tenant_id: uuid.UUID,
    customer_id: uuid.UUID,
    body: NoteCreateRequest,
    membership: CurrentMembership = Depends(require_permission(Permission.CUSTOMERS_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    note = await service.add_note(
        db, tenant_id=tenant_id, customer_id=customer_id, note=body.note, actor_user_id=membership.user_id
    )
    return success({"id": str(note.id), "note": note.note, "created_at": note.created_at.isoformat()})


@router.post("/{customer_id}/tags")
async def add_tag(
    tenant_id: uuid.UUID,
    customer_id: uuid.UUID,
    body: TagCreateRequest,
    membership: CurrentMembership = Depends(require_permission(Permission.CUSTOMERS_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    tag = await service.add_tag(
        db, tenant_id=tenant_id, customer_id=customer_id, tag=body.tag, actor_user_id=membership.user_id
    )
    return success({"id": str(tag.id), "tag": tag.tag})


@router.delete("/{customer_id}/tags/{tag}")
async def remove_tag(
    tenant_id: uuid.UUID,
    customer_id: uuid.UUID,
    tag: str,
    membership: CurrentMembership = Depends(require_permission(Permission.CUSTOMERS_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await service.remove_tag(
        db, tenant_id=tenant_id, customer_id=customer_id, tag=tag, actor_user_id=membership.user_id
    )
    return success({"removed": True})
