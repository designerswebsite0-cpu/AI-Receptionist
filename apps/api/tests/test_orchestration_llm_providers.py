"""Pure-logic tests for the LLM provider abstraction — no network access,
no database. MockLLMProvider/FallbackLLMProvider never call a real API.
"""

import pytest

from app.orchestration.llm.base import LLMMessage, LLMProvider, LLMProviderError, LLMResult
from app.orchestration.llm.fallback import AllProvidersFailedError, FallbackLLMProvider
from app.orchestration.llm.mock_provider import MockLLMProvider


class _AlwaysFailsProvider(LLMProvider):
    name = "always_fails"
    model = "fails-model"

    def __init__(self):
        self.calls = 0

    async def complete(self, messages, **kwargs):
        self.calls += 1
        raise LLMProviderError("simulated outage")


class _AlwaysSucceedsProvider(LLMProvider):
    name = "always_succeeds"
    model = "succeeds-model"

    def __init__(self):
        self.calls = 0

    async def complete(self, messages, **kwargs):
        self.calls += 1
        return LLMResult(text="ok", provider=self.name, model=self.model, latency_ms=1)


# --- MockLLMProvider ---------------------------------------------------------


@pytest.mark.asyncio
async def test_mock_provider_default_stub_response():
    provider = MockLLMProvider()
    result = await provider.complete([LLMMessage(role="user", content="hello")])
    assert result.provider == "mock"
    assert result.text


@pytest.mark.asyncio
async def test_mock_provider_uses_responder_function():
    def responder(messages: list[LLMMessage]) -> LLMResult:
        return LLMResult(text=f"echo: {messages[-1].content}", provider="mock", model="mock-llm", latency_ms=0)

    provider = MockLLMProvider(responder=responder)
    result = await provider.complete([LLMMessage(role="user", content="check-in time?")])
    assert result.text == "echo: check-in time?"


@pytest.mark.asyncio
async def test_mock_provider_cycles_through_canned_responses():
    responses = [
        LLMResult(text="first", provider="mock", model="mock-llm", latency_ms=0),
        LLMResult(text="second", provider="mock", model="mock-llm", latency_ms=0),
    ]
    provider = MockLLMProvider(responses=responses)

    first = await provider.complete([LLMMessage(role="user", content="a")])
    second = await provider.complete([LLMMessage(role="user", content="b")])
    third = await provider.complete([LLMMessage(role="user", content="c")])  # beyond queue length

    assert first.text == "first"
    assert second.text == "second"
    assert third.text == "second"  # holds the last configured response, doesn't crash
    assert provider.call_count == 3


# --- FallbackLLMProvider -----------------------------------------------------


@pytest.mark.asyncio
async def test_fallback_uses_primary_when_healthy():
    primary = _AlwaysSucceedsProvider()
    fallback = MockLLMProvider()
    provider = FallbackLLMProvider(primary=primary, fallback=fallback)

    result = await provider.complete([LLMMessage(role="user", content="hi")])

    assert result.provider == "always_succeeds"
    assert primary.calls == 1


@pytest.mark.asyncio
async def test_fallback_switches_to_fallback_on_primary_failure():
    primary = _AlwaysFailsProvider()
    fallback = MockLLMProvider(responses=[LLMResult(text="fallback", provider="mock", model="mock-llm", latency_ms=0)])
    provider = FallbackLLMProvider(primary=primary, fallback=fallback, failure_threshold=5)

    result = await provider.complete([LLMMessage(role="user", content="hi")])

    assert result.provider == "mock"
    assert primary.calls == 1


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_threshold_and_skips_primary():
    primary = _AlwaysFailsProvider()
    fallback = MockLLMProvider(responses=[LLMResult(text="fallback", provider="mock", model="mock-llm", latency_ms=0)])
    provider = FallbackLLMProvider(primary=primary, fallback=fallback, failure_threshold=2, cooldown_seconds=60)

    for _ in range(4):
        await provider.complete([LLMMessage(role="user", content="hi")])

    # Only the first 2 calls actually hit the failing primary — after the
    # threshold trips, the circuit breaker skips it entirely.
    assert primary.calls == 2


@pytest.mark.asyncio
async def test_fallback_raises_when_both_providers_fail():
    primary = _AlwaysFailsProvider()

    class _AlwaysFailsFallback(LLMProvider):
        name = "fallback_fails"
        model = "fails"

        async def complete(self, messages, **kwargs):
            raise LLMProviderError("fallback also down")

    provider = FallbackLLMProvider(primary=primary, fallback=_AlwaysFailsFallback(), failure_threshold=5)

    with pytest.raises(AllProvidersFailedError):
        await provider.complete([LLMMessage(role="user", content="hi")])
