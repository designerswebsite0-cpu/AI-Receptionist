import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import PageParams, build_page_meta
from app.common.responses import success
from app.conversations import repository as conversations_repository
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
from app.deps import get_current_user
from app.users.models import User

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


@router.post("")
async def create_customer(
    body: CustomerCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    customer = await service.create_customer(db, body=body, actor_user_id=user.id)
    return success(CustomerOut.model_validate(customer).model_dump(mode="json"))


@router.get("")
async def list_customers(
    search: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    params = PageParams(page=page, page_size=page_size)
    customers, total = await repository.search_customers(
        db, search=search, tag=tag, offset=params.offset, limit=params.page_size
    )

    customer_ids = [c.id for c in customers]
    conversation_stats = await conversations_repository.get_conversation_stats_by_customer(db, customer_ids)
    tags_by_customer = await repository.get_tags_by_customer_ids(db, customer_ids)
    contacts_by_customer = await repository.get_contacts_by_customer_ids(db, customer_ids)

    items = []
    for c in customers:
        payload = CustomerOut.model_validate(c).model_dump(mode="json")
        conversation_count, last_message_at = conversation_stats.get(c.id, (0, None))
        payload["tags"] = tags_by_customer.get(c.id, [])
        payload["is_vip"] = "vip" in payload["tags"]
        payload["conversation_count"] = conversation_count
        payload["last_interaction_at"] = last_message_at.isoformat() if last_message_at else None
        contacts = contacts_by_customer.get(c.id, [])
        primary_contact = next((ct for ct in contacts if ct.is_primary), contacts[0] if contacts else None)
        payload["primary_contact"] = (
            {"contact_type": primary_contact.contact_type, "value": primary_contact.value}
            if primary_contact
            else None
        )
        items.append(payload)

    return success({"items": items, "meta": build_page_meta(params, total).model_dump()})


@router.get("/{customer_id}")
async def get_customer(
    customer_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    customer = await service.get_customer_or_404(db, customer_id)
    contacts = await repository.list_contacts(db, customer_id)
    tags = await repository.list_tags(db, customer_id)
    conversation_stats = await conversations_repository.get_conversation_stats_by_customer(db, [customer_id])
    conversation_count, last_message_at = conversation_stats.get(customer_id, (0, None))

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
    payload["is_vip"] = "vip" in payload["tags"]
    payload["conversation_count"] = conversation_count
    payload["last_interaction_at"] = last_message_at.isoformat() if last_message_at else None
    return success(payload)


@router.patch("/{customer_id}")
async def update_customer(
    customer_id: uuid.UUID,
    body: CustomerUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    customer = await service.update_customer(db, customer_id=customer_id, body=body, actor_user_id=user.id)
    return success(CustomerOut.model_validate(customer).model_dump(mode="json"))


@router.post("/{customer_id}/contacts")
async def add_contact(
    customer_id: uuid.UUID,
    body: ContactIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    contact = await service.add_contact(db, customer_id=customer_id, body=body, actor_user_id=user.id)
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
    customer_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    notes = await repository.list_notes(db, customer_id)
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
    customer_id: uuid.UUID,
    body: NoteCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    note = await service.add_note(db, customer_id=customer_id, note=body.note, actor_user_id=user.id)
    return success({"id": str(note.id), "note": note.note, "created_at": note.created_at.isoformat()})


@router.post("/{customer_id}/tags")
async def add_tag(
    customer_id: uuid.UUID,
    body: TagCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    tag = await service.add_tag(db, customer_id=customer_id, tag=body.tag, actor_user_id=user.id)
    return success({"id": str(tag.id), "tag": tag.tag})


@router.delete("/{customer_id}/tags/{tag}")
async def remove_tag(
    customer_id: uuid.UUID,
    tag: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await service.remove_tag(db, customer_id=customer_id, tag=tag, actor_user_id=user.id)
    return success({"removed": True})
