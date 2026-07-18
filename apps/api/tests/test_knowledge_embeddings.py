"""Pure-logic tests for MockEmbeddingProvider — no external API calls,
per the Phase 3 brief's testing requirements. Real OpenAIEmbeddingProvider
behavior is exercised only by the RKPR import CLI script's --execute path
against the live API, never in the automated test suite.
"""

import math

import pytest

from app.knowledge.embeddings import MockEmbeddingProvider, embed_texts


@pytest.mark.asyncio
async def test_mock_provider_is_deterministic_for_identical_text():
    provider = MockEmbeddingProvider(dimensions=64)
    first = await provider.embed_batch(["check-in is at 2pm"])
    second = await provider.embed_batch(["check-in is at 2pm"])
    assert first[0].vector == second[0].vector


@pytest.mark.asyncio
async def test_mock_provider_differs_for_different_text():
    provider = MockEmbeddingProvider(dimensions=64)
    results = await provider.embed_batch(["check-in is at 2pm", "the pool closes at 9pm"])
    assert results[0].vector != results[1].vector


@pytest.mark.asyncio
async def test_mock_provider_vectors_are_unit_normalized():
    provider = MockEmbeddingProvider(dimensions=64)
    [result] = await provider.embed_batch(["some text"])
    norm = math.sqrt(sum(v * v for v in result.vector))
    assert abs(norm - 1.0) < 1e-6


@pytest.mark.asyncio
async def test_embed_texts_batches_large_input_and_preserves_order():
    provider = MockEmbeddingProvider(dimensions=16)
    texts = [f"chunk number {i}" for i in range(250)]  # spans multiple internal batches
    results = await embed_texts(provider, texts)
    assert len(results) == 250
    # Re-embedding the same text individually must match its batched result.
    [solo] = await provider.embed_batch([texts[123]])
    assert results[123].vector == solo.vector


@pytest.mark.asyncio
async def test_embed_texts_empty_list_returns_empty():
    provider = MockEmbeddingProvider()
    assert await embed_texts(provider, []) == []
