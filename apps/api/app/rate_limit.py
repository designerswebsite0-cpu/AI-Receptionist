import time
from collections import defaultdict
from threading import Lock

from fastapi import Request

from app.config import get_settings
from app.errors import RateLimitedError

settings = get_settings()

# In-process, single-replica token bucket. This is an explicit interim
# measure: rules.md §18 requires rate limiting on login now, but the
# Upstash-backed shared limiter isn't wired until Redis lands in Phase 3+
# (see docs/roadmap.md tech debt notes). Do not rely on this across
# multiple API replicas — it does not share state between processes.
_buckets: dict[str, list[float]] = defaultdict(list)
_lock = Lock()


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    client_ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
    return f"{request.url.path}:{client_ip}"


def enforce_rate_limit(request: Request, *, limit_per_minute: int | None = None) -> None:
    limit = limit_per_minute or settings.auth_login_rate_limit_per_minute
    key = _client_key(request)
    now = time.monotonic()
    window_start = now - 60

    with _lock:
        attempts = [ts for ts in _buckets[key] if ts > window_start]
        if len(attempts) >= limit:
            _buckets[key] = attempts
            raise RateLimitedError("Too many requests. Please try again later.")
        attempts.append(now)
        _buckets[key] = attempts
