"""Primary LLM provider — OpenAI, per architecture.md §4.4."""

import json
import time

import openai

from app.config import get_settings
from app.orchestration.llm.base import (
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMResult,
    LLMToolCall,
    to_openai_wire_format,
)


class OpenAILLMProvider(LLMProvider):
    name = "openai"

    def __init__(self, *, api_key: str | None = None, model: str | None = None):
        settings = get_settings()
        self._client = openai.AsyncOpenAI(api_key=api_key or settings.openai_api_key, max_retries=2)
        self.model = model or settings.openai_model

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[dict] | None = None,
        response_format: dict | None = None,
        timeout: float = 20.0,
    ) -> LLMResult:
        started_at = time.monotonic()
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=[to_openai_wire_format(m) for m in messages],
                tools=tools,
                response_format=response_format,
                timeout=timeout,
            )
        except openai.APIError as exc:
            raise LLMProviderError(f"OpenAI request failed: {exc}") from exc

        latency_ms = int((time.monotonic() - started_at) * 1000)
        choice = response.choices[0]
        tool_calls = [
            LLMToolCall(
                call_id=call.id, tool_name=call.function.name, arguments=_safe_json_loads(call.function.arguments)
            )
            for call in (choice.message.tool_calls or [])
        ]

        return LLMResult(
            text=choice.message.content or "",
            provider=self.name,
            model=self.model,
            latency_ms=latency_ms,
            prompt_tokens=response.usage.prompt_tokens if response.usage else None,
            completion_tokens=response.usage.completion_tokens if response.usage else None,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason,
        )


def _safe_json_loads(raw: str) -> dict:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
