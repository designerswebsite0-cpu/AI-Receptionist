"""LLM provider abstraction. Orchestration code (intent classification,
prompt builder, tool-call proposal) depends only on this protocol —
never on `openai`/Groq SDK types directly — so swapping or adding a
provider never touches calling code, matching the established pattern
from app.knowledge.embeddings.EmbeddingProvider.
"""

import json
from dataclasses import dataclass, field


@dataclass
class LLMToolCall:
    call_id: str  # the provider's own id for this proposed call — required
    # to correlate a follow-up "tool" role message back to it (OpenAI's API
    # rejects a "tool" message that isn't a reply to a preceding message
    # carrying a matching tool_calls[].id; a real, previously-undiscovered
    # bug this exact gap caused — see app.orchestration.pipeline).
    tool_name: str
    arguments: dict


@dataclass
class LLMMessage:
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    # Only set on an assistant message that proposed tool calls (needed to
    # replay that exact proposal back to the API) or a tool message
    # answering one (needed to say which call_id this result is for).
    tool_calls: list[LLMToolCall] | None = None
    tool_call_id: str | None = None


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    latency_ms: int
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    tool_calls: list[LLMToolCall] = field(default_factory=list)
    finish_reason: str | None = None


class LLMProviderError(Exception):
    """Raised by a provider implementation on timeout/rate-limit/API
    error — callers (app.orchestration.llm.fallback) catch this
    specifically to decide whether to fail over, never a bare Exception."""


class LLMProvider:
    name: str
    model: str

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[dict] | None = None,
        response_format: dict | None = None,
        timeout: float = 20.0,
    ) -> LLMResult:
        raise NotImplementedError


def to_openai_wire_format(message: LLMMessage) -> dict:
    """Shared by OpenAILLMProvider and GroqLLMProvider (Groq's API is
    OpenAI-compatible at the wire level). A naive {role, content} dict
    silently violates OpenAI's actual message-format contract the first
    time a real tool round-trip happens: the API rejects a "tool" role
    message unless the immediately preceding message carries a matching
    tool_calls[].id, and rejects replaying an assistant's tool proposal
    unless it's back in the tool_calls[] field, not just as text. Mocks
    never enforce this, so this gap only surfaced via the Phase 4
    real-data validation checklist against the real API.
    """
    payload: dict = {"role": message.role, "content": message.content}
    if message.tool_calls:
        payload["tool_calls"] = [
            {
                "id": call.call_id,
                "type": "function",
                "function": {"name": call.tool_name, "arguments": json.dumps(call.arguments)},
            }
            for call in message.tool_calls
        ]
    if message.tool_call_id:
        payload["tool_call_id"] = message.tool_call_id
    return payload
