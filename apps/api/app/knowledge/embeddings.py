"""Embedding providers. OpenAIEmbeddingProvider is the real, production
path; MockEmbeddingProvider is a deterministic, hash-seeded fake used by
tests so the suite never makes an external paid API call (Phase 3 brief's
testing requirements) — same input text always yields the same vector,
so cosine-similarity assertions in tests are reproducible.
"""

import hashlib
import math
import random
from dataclasses import dataclass

import openai

from app.config import get_settings
from app.errors import ValidationErrorApp
from app.knowledge.constants import EMBEDDING_DIMENSIONS


@dataclass
class EmbeddingResult:
    vector: list[float]
    model: str


class EmbeddingProvider:
    model: str

    async def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        raise NotImplementedError


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, *, api_key: str | None = None, model: str | None = None, dimensions: int | None = None):
        settings = get_settings()
        self._client = openai.AsyncOpenAI(api_key=api_key or settings.openai_api_key)
        self.model = model or settings.openai_embedding_model
        # Truncated via OpenAI's `dimensions` param, not just column
        # width — see EMBEDDING_DIMENSIONS' docstring (pgvector's HNSW
        # index caps at 2000 dims, below -3-large's native 3072).
        self.dimensions = dimensions or EMBEDDING_DIMENSIONS

    async def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        if not texts:
            return []
        response = await self._client.embeddings.create(
            model=self.model, input=texts, dimensions=self.dimensions
        )
        return [EmbeddingResult(vector=item.embedding, model=self.model) for item in response.data]


class MockEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dimensions: int = EMBEDDING_DIMENSIONS):
        self.dimensions = dimensions
        self.model = "mock-embedding"

    async def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> EmbeddingResult:
        seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
        rng = random.Random(seed)
        vector = [rng.uniform(-1.0, 1.0) for _ in range(self.dimensions)]
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return EmbeddingResult(vector=[v / norm for v in vector], model=self.model)


_EMBED_BATCH_SIZE = 96


async def embed_texts(provider: EmbeddingProvider, texts: list[str]) -> list[EmbeddingResult]:
    """Batches requests — OpenAI's embeddings endpoint accepts many inputs
    per call, but an unbounded batch risks hitting request-size limits on
    a large corpus; 96 keeps well under them while still amortizing
    per-request overhead."""
    results: list[EmbeddingResult] = []
    for offset in range(0, len(texts), _EMBED_BATCH_SIZE):
        batch = texts[offset : offset + _EMBED_BATCH_SIZE]
        results.extend(await provider.embed_batch(batch))
    return results


def get_embedding_provider() -> EmbeddingProvider:
    """FastAPI dependency for live HTTP endpoints (upload, search). Fails
    loudly rather than silently falling back to MockEmbeddingProvider —
    that fallback exists only for the test suite, never for a real
    request that would embed actual guest-facing content with fake,
    non-semantic vectors."""
    settings = get_settings()
    if not settings.openai_api_key:
        raise ValidationErrorApp("OPENAI_API_KEY is not configured — cannot generate embeddings")
    return OpenAIEmbeddingProvider()
