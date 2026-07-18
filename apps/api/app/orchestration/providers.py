"""FastAPI dependency factories for the real providers the orchestration
pipeline needs. Fails loudly (ValidationErrorApp) rather than silently
falling back to a mock if not configured — mirrors
app.knowledge.embeddings.get_embedding_provider's own precedent: mocks are
test-only, never a silent substitute for a real guest-facing request.
"""

from app.config import get_settings
from app.errors import ValidationErrorApp
from app.knowledge.embeddings import EmbeddingProvider, get_embedding_provider
from app.knowledge.retrieval.reranker import HeuristicReranker, Reranker
from app.orchestration.llm.base import LLMProvider
from app.orchestration.llm.fallback import FallbackLLMProvider
from app.orchestration.llm.groq_provider import GroqLLMProvider
from app.orchestration.llm.openai_provider import OpenAILLMProvider


def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if not settings.openai_api_key:
        raise ValidationErrorApp("OPENAI_API_KEY is not configured — the orchestration pipeline needs a real LLM.")

    primary = OpenAILLMProvider()
    if not settings.groq_api_key:
        # No fallback configured — run on the primary alone rather than
        # silently constructing a Groq client with no valid key, which
        # would only fail later, at request time, in a more confusing way.
        return primary
    return FallbackLLMProvider(primary=primary, fallback=GroqLLMProvider())


def get_orchestration_embedding_provider() -> EmbeddingProvider:
    return get_embedding_provider()


def get_reranker() -> Reranker:
    return HeuristicReranker()
