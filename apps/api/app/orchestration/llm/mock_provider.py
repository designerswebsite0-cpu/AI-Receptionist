"""Deterministic LLM provider for tests — never makes a network call.
Unlike MockEmbeddingProvider (where any consistent vector suffices for
similarity tests), text-output tests need actual *control* over what the
"model" says — so this takes an explicit responder function or a
canned-response queue, defaulting to a fixed, clearly-labeled stub answer
if neither is configured.
"""

from collections.abc import Callable

from app.orchestration.llm.base import LLMMessage, LLMProvider, LLMResult

_DEFAULT_STUB_TEXT = "[mock-llm-response]"


class MockLLMProvider(LLMProvider):
    name = "mock"
    model = "mock-llm"

    def __init__(
        self,
        *,
        responder: Callable[[list[LLMMessage]], LLMResult] | None = None,
        responses: list[LLMResult] | None = None,
    ):
        self._responder = responder
        self._responses = list(responses) if responses else None
        self._call_count = 0

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[dict] | None = None,
        response_format: dict | None = None,
        timeout: float = 20.0,
    ) -> LLMResult:
        self._call_count += 1

        if self._responder is not None:
            return self._responder(messages)

        if self._responses is not None:
            index = min(self._call_count - 1, len(self._responses) - 1)
            return self._responses[index]

        return LLMResult(text=_DEFAULT_STUB_TEXT, provider=self.name, model=self.model, latency_ms=0)

    @property
    def call_count(self) -> int:
        return self._call_count
