"""Customer 360 foundation tests. Requires a reachable Postgres (see
conftest.db_engine); skips cleanly when none is available.

Single-resort deployment (product_decisions.md): no tenant_id anywhere —
these tests exercise the service layer directly against a plain session.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.customers import service
from app.customers.schemas import ContactIn, CustomerCreateRequest, CustomerUpdateRequest
from app.errors import ConflictError, NotFoundError
from app.users.models import User


@pytest.mark.asyncio
async def test_create_customer_with_contacts(db_session: AsyncSession):
    body = CustomerCreateRequest(
        full_name="Jane Guest",
        contacts=[ContactIn(contact_type="whatsapp", value="+15550001111", is_primary=True)],
    )
    customer = await service.create_customer(db_session, body=body, actor_user_id=None)

    assert customer.full_name == "Jane Guest"
    assert customer.preferred_language == "en"


@pytest.mark.asyncio
async def test_duplicate_contact_is_rejected(db_session: AsyncSession):
    body = CustomerCreateRequest(contacts=[ContactIn(contact_type="phone", value="+15550002222")])
    await service.create_customer(db_session, body=body, actor_user_id=None)

    with pytest.raises(ConflictError):
        await service.create_customer(db_session, body=body, actor_user_id=None)


@pytest.mark.asyncio
async def test_update_customer_only_touches_provided_fields(db_session: AsyncSession):
    customer = await service.create_customer(
        db_session, body=CustomerCreateRequest(full_name="Original Name"), actor_user_id=None
    )

    updated = await service.update_customer(
        db_session,
        customer_id=customer.id,
        body=CustomerUpdateRequest(loyalty_reference="GOLD-123"),
        actor_user_id=None,
    )

    assert updated.full_name == "Original Name"
    assert updated.loyalty_reference == "GOLD-123"


@pytest.mark.asyncio
async def test_get_nonexistent_customer_returns_not_found(db_session: AsyncSession):
    with pytest.raises(NotFoundError):
        await service.get_customer_or_404(db_session, uuid.uuid4())


@pytest.mark.asyncio
async def test_tags_are_unique_per_customer(db_session: AsyncSession):
    customer = await service.create_customer(db_session, body=CustomerCreateRequest(), actor_user_id=None)
    await service.add_tag(db_session, customer_id=customer.id, tag="vip", actor_user_id=None)

    with pytest.raises(ConflictError):
        await service.add_tag(db_session, customer_id=customer.id, tag="vip", actor_user_id=None)


@pytest.mark.asyncio
async def test_remove_nonexistent_tag_raises_not_found(db_session: AsyncSession):
    customer = await service.create_customer(db_session, body=CustomerCreateRequest(), actor_user_id=None)

    with pytest.raises(NotFoundError):
        await service.remove_tag(db_session, customer_id=customer.id, tag="nope", actor_user_id=None)


@pytest.mark.asyncio
async def test_notes_are_attributed_to_author(db_session: AsyncSession):
    customer = await service.create_customer(db_session, body=CustomerCreateRequest(), actor_user_id=None)
    author = User(id=uuid.uuid4(), email="staff@example.com")
    db_session.add(author)
    await db_session.flush()
    await db_session.commit()

    note = await service.add_note(
        db_session, customer_id=customer.id, note="Prefers ocean view", actor_user_id=author.id
    )

    assert note.author_user_id == author.id
    assert note.note == "Prefers ocean view"
