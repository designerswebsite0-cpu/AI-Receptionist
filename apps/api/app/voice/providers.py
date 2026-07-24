"""Voice-specific LLM provider ordering — Groq primary / OpenAI 4o-mini
fallback, the REVERSE of app.orchestration.providers.get_llm_provider's
OpenAI-primary/Groq-fallback used by text channels (architecture.md §4.4).
The Phase 9 brief specifies this explicitly for voice, presumably because
Groq's inference latency matters far more on a live phone call than in
chat. Reuses the exact same LLMProvider implementations and
FallbackLLMProvider wrapper as the text pipeline — no second retry/circuit-
breaker implementation.
"""

from app.config import get_settings
from app.errors import ValidationErrorApp
from app.orchestration.llm.base import LLMProvider
from app.orchestration.llm.fallback import FallbackLLMProvider
from app.orchestration.llm.groq_provider import GroqLLMProvider
from app.orchestration.llm.openai_provider import OpenAILLMProvider


def get_voice_llm_provider() -> LLMProvider:
    settings = get_settings()
    if not settings.groq_api_key:
        raise ValidationErrorApp("GROQ_API_KEY is not configured — the voice agent needs a real primary LLM.")

    primary = GroqLLMProvider()
    if not settings.openai_api_key:
        return primary
    return FallbackLLMProvider(primary=primary, fallback=OpenAILLMProvider())
