import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.customers.models import Customer, CustomerContact, CustomerNote, CustomerTag


async def get_customer(db: AsyncSession, customer_id: uuid.UUID) -> Customer | None:
    result = await db.execute(select(Customer).where(Customer.id == customer_id, Customer.deleted_at.is_(None)))
    return result.scalar_one_or_none()


async def search_customers(
    db: AsyncSession,
    *,
    search: str | None,
    tag: str | None,
    offset: int,
    limit: int,
) -> tuple[list[Customer], int]:
    query = select(Customer).where(Customer.deleted_at.is_(None))
    count_query = select(func.count()).select_from(Customer).where(Customer.deleted_at.is_(None))

    if search:
        pattern = f"%{search}%"
        contact_match = select(CustomerContact.customer_id).where(CustomerContact.value.ilike(pattern))
        condition = or_(Customer.full_name.ilike(pattern), Customer.id.in_(contact_match))
        query = query.where(condition)
        count_query = count_query.where(condition)

    if tag:
        tag_match = select(CustomerTag.customer_id).where(CustomerTag.tag == tag)
        query = query.where(Customer.id.in_(tag_match))
        count_query = count_query.where(Customer.id.in_(tag_match))

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(query.order_by(Customer.created_at.desc()).offset(offset).limit(limit))
    return list(result.scalars().all()), total


async def list_contacts(db: AsyncSession, customer_id: uuid.UUID) -> list[CustomerContact]:
    result = await db.execute(select(CustomerContact).where(CustomerContact.customer_id == customer_id))
    return list(result.scalars().all())


async def find_customer_by_contact(db: AsyncSession, contact_type: str, value: str) -> Customer | None:
    """Identity resolution: the same phone/email/WhatsApp id always maps to
    one customer — architecture.md §4.2. Single-resort, so this lookup is
    global to the deployment rather than scoped to a tenant."""
    result = await db.execute(
        select(Customer)
        .join(CustomerContact, CustomerContact.customer_id == Customer.id)
        .where(
            CustomerContact.contact_type == contact_type,
            CustomerContact.value == value,
            Customer.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def list_notes(db: AsyncSession, customer_id: uuid.UUID) -> list[CustomerNote]:
    result = await db.execute(
        select(CustomerNote).where(CustomerNote.customer_id == customer_id).order_by(CustomerNote.created_at.desc())
    )
    return list(result.scalars().all())


async def list_tags(db: AsyncSession, customer_id: uuid.UUID) -> list[CustomerTag]:
    result = await db.execute(select(CustomerTag).where(CustomerTag.customer_id == customer_id))
    return list(result.scalars().all())


async def get_tag(db: AsyncSession, customer_id: uuid.UUID, tag: str) -> CustomerTag | None:
    result = await db.execute(
        select(CustomerTag).where(CustomerTag.customer_id == customer_id, CustomerTag.tag == tag)
    )
    return result.scalar_one_or_none()
