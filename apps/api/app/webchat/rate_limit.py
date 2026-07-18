"""Redis-backed fixed-window rate limiting for the public webchat surface.

Unlike app.rate_limit (an explicitly single-replica, in-process interim
measure documented there for the login endpoint only), this is the
general-purpose abuse guard the Phase 5 brief requires: an anonymous,
unauthenticated endpoint that triggers real paid LLM calls is a direct
cost-abuse surface, and rate limiting it must work across replicas.

Fails OPEN if Redis is unreachable or unconfigured: a guest's chat must
never hard-fail just because an optional shared counter store is briefly
down. This is a deliberate, documented tradeoff (brief: "Use Redis when
appropriate, but fail safely if Redis is temporarily unavailable") — the
message-length and session-auth checks still apply regardless.
"""

import redis.asyncio as aioredis

from app.config import get_settings
from app.errors import RateLimitedError
from app.logging import get_logger

logger = get_logger(__name__)

_client: aioredis.Redis | None = None
_client_init_attempted = False


def _get_client() -> aioredis.Redis | None:
    global _client, _client_init_attempted
    if _client_init_attempted:
        return _client
    _client_init_attempted = True
    settings = get_settings()
    if not settings.redis_url:
        logger.warning("webchat_rate_limit_redis_unconfigured — proceeding without shared rate limiting")
        return None
    _client = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _client


async def enforce(key: str, *, limit: int, window_seconds: int) -> None:
    """Increments `key`'s fixed-window counter and raises RateLimitedError
    if it exceeds `limit` within `window_seconds`. A fixed window (not a
    sliding one) is an intentional simplicity tradeoff — sufficient to stop
    sustained abuse/cost-runaway without needing a Lua script for exact
    sliding-window semantics."""
    client = _get_client()
    if client is None:
        return
    try:
        current = await client.incr(key)
        if current == 1:
            await client.expire(key, window_seconds)
    except RateLimitedError:
        raise
    except Exception:
        logger.exception("webchat_rate_limit_check_failed key=%s", key)
        return
    else:
        if current > limit:
            raise RateLimitedError("Too many requests. Please slow down and try again shortly.")


def client_ip(forwarded_for: str | None, direct_host: str | None) -> str:
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return direct_host or "unknown"
