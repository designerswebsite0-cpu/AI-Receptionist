"""Wraps a primary + fallback LLMProvider pair with retry-on-failure and a
simple circuit breaker: after N consecutive primary failures, the primary
is skipped (calls go straight to fallback) for a cooldown window, rather
than paying the primary's timeout on every single request while it's
known to be down.
"""

import time

from app.config import get_settings
from app.errors import AppError
from app.orchestration.llm.base import LLMMessage, LLMProvider, LLMProviderError, LLMResult


class AllProvidersFailedError(AppError):
    code = "LLM_PROVIDERS_UNAVAILABLE"
    status_code = 502


class FallbackLLMProvider(LLMProvider):
    name = "fallback"

    def __init__(
        self,
        *,
        primary: LLMProvider,
        fallback: LLMProvider,
        failure_threshold: int | None = None,
        cooldown_seconds: int | None = None,
    ):
        settings = get_settings()
        self._primary = primary
        self._fallback = fallback
        self._failure_threshold = failure_threshold or settings.orchestration_provider_failure_threshold
        self._cooldown_seconds = cooldown_seconds or settings.orchestration_provider_cooldown_seconds
        self._consecutive_failures = 0
        self._disabled_until: float | None = None

    @property
    def model(self) -> str:  # not fixed — depends on which provider actually served the request
        return self._primary.model

    def _primary_is_available(self) -> bool:
        if self._disabled_until is None:
            return True
        if time.monotonic() >= self._disabled_until:
            # Cooldown elapsed — give the primary another chance rather
            # than staying disabled forever on a transient outage.
            self._disabled_until = None
            self._consecutive_failures = 0
            return True
        return False

    def _record_primary_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._failure_threshold:
            self._disabled_until = time.monotonic() + self._cooldown_seconds

    def _record_primary_success(self) -> None:
        self._consecutive_failures = 0
        self._disabled_until = None

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[dict] | None = None,
        response_format: dict | None = None,
        timeout: float = 20.0,
    ) -> LLMResult:
        if self._primary_is_available():
            try:
                result = await self._primary.complete(
                    messages, tools=tools, response_format=response_format, timeout=timeout
                )
                self._record_primary_success()
                return result
            except LLMProviderError:
                self._record_primary_failure()

        try:
            return await self._fallback.complete(
                messages, tools=tools, response_format=response_format, timeout=timeout
            )
        except LLMProviderError as exc:
            raise AllProvidersFailedError("Both primary and fallback LLM providers failed") from exc
