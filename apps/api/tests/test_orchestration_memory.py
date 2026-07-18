"""Tests for app.orchestration.memory — the controlled Customer 360 memory
layer (rules.md §6: verified facts, AI inferences, and AI summaries are
stored and read back separately; an AI inference must never overwrite a
verified fact). Requires a reachable Postgres (see conftest.db_session);
skips cleanly when none is available.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.customers import service as customer_service
from app.customers.schemas import CustomerCreateRequest
from app.orchestration.domain import ExtractedEntities
from app.orchestration.memory import DURABLE_MEMORY_FIELDS, assemble_memory_context, record_inferences


async def _make_customer(db: AsyncSession):
    return await customer_service.create_customer(
        db, body=CustomerCreateRequest(full_name="Jane Guest"), actor_user_id=None
    )


@pytest.mark.asyncio
async def test_record_inferences_only_stores_durable_whitelisted_fields(db_session: AsyncSession):
    customer = await _make_customer(db_session)
    entities = ExtractedEntities(
        values={"dietary_restrictions": "vegan", "check_in_date": "15 July 2026", "budget": 50000},
        confidence={"dietary_restrictions": 0.9, "check_in_date": 1.0, "budget": 0.9},
        source={"dietary_restrictions": "llm", "check_in_date": "deterministic", "budget": "deterministic"},
    )

    recorded = await record_inferences(db_session, customer=customer, entities=entities, conversation_id=uuid.uuid4())

    assert recorded == ["dietary_restrictions"]
    assert "dietary_restrictions" in DURABLE_MEMORY_FIELDS
    # stay-specific fields (check_in_date, budget) are never written, even
    # at high confidence -- they'd be wrong for a future, unrelated stay.
    assert "check_in_date" not in DURABLE_MEMORY_FIELDS
    assert "budget" not in DURABLE_MEMORY_FIELDS


@pytest.mark.asyncio
async def test_record_inferences_skips_low_confidence_facts(db_session: AsyncSession):
    customer = await _make_customer(db_session)
    entities = ExtractedEntities(
        values={"view_preference": "ocean"}, confidence={"view_preference": 0.4}, source={"view_preference": "llm"}
    )

    recorded = await record_inferences(db_session, customer=customer, entities=entities, conversation_id=uuid.uuid4())

    assert recorded == []
    context = await assemble_memory_context(db_session, customer=customer)
    assert context["ai_inferred"] == {}


@pytest.mark.asyncio
async def test_record_inferences_never_touches_verified_customer_fields(db_session: AsyncSession):
    """The whole point of rules.md §6: an AI inference must never overwrite
    verified data -- record_inferences only ever writes into the
    ai_inferred sub-key, never full_name/preferred_language directly."""
    customer = await _make_customer(db_session)
    original_name = customer.full_name

    entities = ExtractedEntities(
        values={"guest_name": "Someone Else"}, confidence={"guest_name": 0.95}, source={"guest_name": "llm"}
    )
    await record_inferences(db_session, customer=customer, entities=entities, conversation_id=uuid.uuid4())

    await db_session.refresh(customer)
    assert customer.full_name == original_name  # untouched -- verified field, never overwritten

    context = await assemble_memory_context(db_session, customer=customer)
    assert context["verified"]["full_name"] == original_name
    assert context["ai_inferred"]["guest_name"]["value"] == "Someone Else"  # recorded, but only as an inference


@pytest.mark.asyncio
async def test_later_conversation_overwrites_earlier_inference_for_same_field(db_session: AsyncSession):
    """Guests are allowed to change their mind -- recency wins for the AI's
    own inferences (this never touches verified data either way)."""
    customer = await _make_customer(db_session)

    first = ExtractedEntities(
        values={"view_preference": "ocean"}, confidence={"view_preference": 0.8}, source={"view_preference": "llm"}
    )
    await record_inferences(db_session, customer=customer, entities=first, conversation_id=uuid.uuid4())

    second = ExtractedEntities(
        values={"view_preference": "garden"}, confidence={"view_preference": 0.7}, source={"view_preference": "llm"}
    )
    await record_inferences(db_session, customer=customer, entities=second, conversation_id=uuid.uuid4())

    context = await assemble_memory_context(db_session, customer=customer)
    assert context["ai_inferred"]["view_preference"]["value"] == "garden"


@pytest.mark.asyncio
async def test_assemble_memory_context_includes_staff_notes_in_verified_bucket(db_session: AsyncSession):
    customer = await _make_customer(db_session)
    await customer_service.add_note(
        db_session, customer_id=customer.id, note="Allergic to shellfish", actor_user_id=None
    )

    context = await assemble_memory_context(db_session, customer=customer)

    assert "Allergic to shellfish" in context["verified"]["staff_notes"]
