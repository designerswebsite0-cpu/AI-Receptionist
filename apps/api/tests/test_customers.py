"""Customer 360 foundation tests. Requires a reachable Postgres (see
conftest.db_engine); skips cleanly when none is available.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.customers import service
from app.customers.schemas import ContactIn, CustomerCreateRequest, CustomerUpdateRequest
from app.errors import ConflictError, NotFoundError
from app.tenants.models import Tenant
from app.users.models import User


@pytest.mark.asyncio
async def test_create_customer_with_contacts(db_session: AsyncSession):
    tenant = Tenant(name="Resort A", slug="resort-a")
    db_session.add(tenant)
    await db_session.flush()
    await db_session.commit()

    body = CustomerCreateRequest(
        full_name="Jane Guest",
        contacts=[ContactIn(contact_type="whatsapp", value="+15550001111", is_primary=True)],
    )
    customer = await service.create_customer(db_session, tenant_id=tenant.id, body=body, actor_user_id=None)

    assert customer.full_name == "Jane Guest"
    assert customer.preferred_language == "en"


@pytest.mark.asyncio
async def test_duplicate_contact_within_tenant_is_rejected(db_session: AsyncSession):
    tenant = Tenant(name="Resort B", slug="resort-b")
    db_session.add(tenant)
    await db_session.flush()
    await db_session.commit()

    body = CustomerCreateRequest(contacts=[ContactIn(contact_type="phone", value="+15550002222")])
    await service.create_customer(db_session, tenant_id=tenant.id, body=body, actor_user_id=None)

    with pytest.raises(ConflictError):
        await service.create_customer(db_session, tenant_id=tenant.id, body=body, actor_user_id=None)


@pytest.mark.asyncio
async def test_same_contact_value_allowed_across_different_tenants(db_session: AsyncSession):
    tenant_a = Tenant(name="Resort C", slug="resort-c")
    tenant_b = Tenant(name="Resort D", slug="resort-d")
    db_session.add_all([tenant_a, tenant_b])
    await db_session.flush()
    await db_session.commit()

    body = CustomerCreateRequest(contacts=[ContactIn(contact_type="phone", value="+15550003333")])
    a = await service.create_customer(db_session, tenant_id=tenant_a.id, body=body, actor_user_id=None)
    b = await service.create_customer(db_session, tenant_id=tenant_b.id, body=body, actor_user_id=None)

    assert a.id != b.id


@pytest.mark.asyncio
async def test_update_customer_only_touches_provided_fields(db_session: AsyncSession):
    tenant = Tenant(name="Resort E", slug="resort-e")
    db_session.add(tenant)
    await db_session.flush()
    await db_session.commit()

    customer = await service.create_customer(
        db_session, tenant_id=tenant.id, body=CustomerCreateRequest(full_name="Original Name"), actor_user_id=None
    )

    updated = await service.update_customer(
        db_session,
        tenant_id=tenant.id,
        customer_id=customer.id,
        body=CustomerUpdateRequest(loyalty_reference="GOLD-123"),
        actor_user_id=None,
    )

    assert updated.full_name == "Original Name"
    assert updated.loyalty_reference == "GOLD-123"


@pytest.mark.asyncio
async def test_get_customer_from_wrong_tenant_returns_not_found(db_session: AsyncSession):
    tenant_a = Tenant(name="Resort F", slug="resort-f")
    tenant_b = Tenant(name="Resort G", slug="resort-g")
    db_session.add_all([tenant_a, tenant_b])
    await db_session.flush()
    await db_session.commit()

    customer = await service.create_customer(
        db_session, tenant_id=tenant_a.id, body=CustomerCreateRequest(full_name="A's Guest"), actor_user_id=None
    )

    with pytest.raises(NotFoundError):
        await service.get_customer_or_404(db_session, tenant_b.id, customer.id)


@pytest.mark.asyncio
async def test_tags_are_unique_per_customer(db_session: AsyncSession):
    tenant = Tenant(name="Resort H", slug="resort-h")
    db_session.add(tenant)
    await db_session.flush()
    await db_session.commit()

    customer = await service.create_customer(
        db_session, tenant_id=tenant.id, body=CustomerCreateRequest(), actor_user_id=None
    )
    await service.add_tag(db_session, tenant_id=tenant.id, customer_id=customer.id, tag="vip", actor_user_id=None)

    with pytest.raises(ConflictError):
        await service.add_tag(db_session, tenant_id=tenant.id, customer_id=customer.id, tag="vip", actor_user_id=None)


@pytest.mark.asyncio
async def test_remove_nonexistent_tag_raises_not_found(db_session: AsyncSession):
    tenant = Tenant(name="Resort I", slug="resort-i")
    db_session.add(tenant)
    await db_session.flush()
    await db_session.commit()

    customer = await service.create_customer(
        db_session, tenant_id=tenant.id, body=CustomerCreateRequest(), actor_user_id=None
    )

    with pytest.raises(NotFoundError):
        await service.remove_tag(
            db_session, tenant_id=tenant.id, customer_id=customer.id, tag="nope", actor_user_id=None
        )


@pytest.mark.asyncio
async def test_notes_are_attributed_to_author(db_session: AsyncSession):
    tenant = Tenant(name="Resort J", slug="resort-j")
    db_session.add(tenant)
    await db_session.flush()
    await db_session.commit()

    customer = await service.create_customer(
        db_session, tenant_id=tenant.id, body=CustomerCreateRequest(), actor_user_id=None
    )
    author = User(id=uuid.uuid4(), email="staff@example.com")
    db_session.add(author)
    await db_session.flush()
    await db_session.commit()

    note = await service.add_note(
        db_session, tenant_id=tenant.id, customer_id=customer.id, note="Prefers ocean view", actor_user_id=author.id
    )

    assert note.author_user_id == author.id
    assert note.note == "Prefers ocean view"
