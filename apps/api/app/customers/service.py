import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_audit_event
from app.customers import repository
from app.customers.models import Customer, CustomerContact, CustomerNote, CustomerTag
from app.customers.schemas import ContactIn, CustomerCreateRequest, CustomerUpdateRequest
from app.errors import ConflictError, NotFoundError


async def create_customer(
    db: AsyncSession, *, body: CustomerCreateRequest, actor_user_id: uuid.UUID | None
) -> Customer:
    for contact in body.contacts:
        existing = await repository.find_customer_by_contact(db, contact.contact_type, contact.value)
        if existing is not None:
            raise ConflictError(f"A customer with {contact.contact_type} '{contact.value}' already exists")

    customer = Customer(
        full_name=body.full_name,
        preferred_language=body.preferred_language,
        preferred_channel=body.preferred_channel,
    )
    db.add(customer)
    await db.flush()

    for contact in body.contacts:
        db.add(
            CustomerContact(
                customer_id=customer.id,
                contact_type=contact.contact_type,
                value=contact.value,
                is_primary=contact.is_primary,
                verified=contact.verified,
            )
        )

    await record_audit_event(
        db,
        actor_user_id=actor_user_id,
        action="customer.created",
        resource_type="customer",
        resource_id=str(customer.id),
        after_state={"full_name": body.full_name},
        metadata={"full_name": body.full_name},
    )
    await db.commit()
    await db.refresh(customer)
    return customer


async def get_customer_or_404(db: AsyncSession, customer_id: uuid.UUID) -> Customer:
    customer = await repository.get_customer(db, customer_id)
    if customer is None:
        raise NotFoundError("Customer not found")
    return customer


async def update_customer(
    db: AsyncSession, *, customer_id: uuid.UUID, body: CustomerUpdateRequest, actor_user_id: uuid.UUID | None
) -> Customer:
    customer = await get_customer_or_404(db, customer_id)

    updates = body.model_dump(exclude_unset=True)
    before_state = {field: getattr(customer, field) for field in updates}
    for field, value in updates.items():
        setattr(customer, field, value)

    await record_audit_event(
        db,
        actor_user_id=actor_user_id,
        action="customer.updated",
        resource_type="customer",
        resource_id=str(customer.id),
        before_state=before_state,
        after_state=updates,
        metadata={"fields": list(updates.keys())},
    )
    await db.commit()
    await db.refresh(customer)
    return customer


async def add_contact(
    db: AsyncSession, *, customer_id: uuid.UUID, body: ContactIn, actor_user_id: uuid.UUID | None
) -> CustomerContact:
    await get_customer_or_404(db, customer_id)

    existing = await repository.find_customer_by_contact(db, body.contact_type, body.value)
    if existing is not None:
        raise ConflictError(f"A customer with {body.contact_type} '{body.value}' already exists")

    contact = CustomerContact(
        customer_id=customer_id,
        contact_type=body.contact_type,
        value=body.value,
        is_primary=body.is_primary,
        verified=body.verified,
    )
    db.add(contact)
    await record_audit_event(
        db,
        actor_user_id=actor_user_id,
        action="customer.contact_added",
        resource_type="customer",
        resource_id=str(customer_id),
        metadata={"contact_type": body.contact_type},
    )
    await db.commit()
    await db.refresh(contact)
    return contact


async def add_note(
    db: AsyncSession, *, customer_id: uuid.UUID, note: str, actor_user_id: uuid.UUID | None
) -> CustomerNote:
    await get_customer_or_404(db, customer_id)

    row = CustomerNote(customer_id=customer_id, author_user_id=actor_user_id, note=note)
    db.add(row)
    await record_audit_event(
        db,
        actor_user_id=actor_user_id,
        action="customer.note_added",
        resource_type="customer",
        resource_id=str(customer_id),
        metadata={},
    )
    await db.commit()
    await db.refresh(row)
    return row


async def add_tag(
    db: AsyncSession, *, customer_id: uuid.UUID, tag: str, actor_user_id: uuid.UUID | None
) -> CustomerTag:
    await get_customer_or_404(db, customer_id)

    if await repository.get_tag(db, customer_id, tag) is not None:
        raise ConflictError(f"Tag '{tag}' already exists on this customer")

    row = CustomerTag(customer_id=customer_id, tag=tag)
    db.add(row)
    await record_audit_event(
        db,
        actor_user_id=actor_user_id,
        action="customer.tag_added",
        resource_type="customer",
        resource_id=str(customer_id),
        metadata={"tag": tag},
    )
    await db.commit()
    await db.refresh(row)
    return row


async def remove_tag(db: AsyncSession, *, customer_id: uuid.UUID, tag: str, actor_user_id: uuid.UUID | None) -> None:
    row = await repository.get_tag(db, customer_id, tag)
    if row is None:
        raise NotFoundError("Tag not found")

    await db.delete(row)
    await record_audit_event(
        db,
        actor_user_id=actor_user_id,
        action="customer.tag_removed",
        resource_type="customer",
        resource_id=str(customer_id),
        metadata={"tag": tag},
    )
    await db.commit()
