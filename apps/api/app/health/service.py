"""Settings hub support (Phase X Stage 8): Integrations and System
Monitoring both read real configuration/connectivity only — never a
stack trace, an env var dump, or a fabricated "all systems operational"
banner. A masked API key fragment (first 4 + last 4 characters) is the
most any caller ever sees of a real secret; the raw value never leaves
app.config.Settings.
"""

from urllib.parse import urlparse

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings


def _mask(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "•" * len(value)
    return f"{value[:4]}…{value[-4:]}"


async def _database_reachable(db: AsyncSession) -> bool:
    try:
        await db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def get_integrations_status(db: AsyncSession) -> dict:
    settings = get_settings()
    db_ok = await _database_reachable(db)

    return {
        "supabase": {
            "configured": True,
            "reachable": db_ok,
            "project_host": urlparse(settings.supabase_url).hostname,
        },
        "openai": {
            "configured": bool(settings.openai_api_key),
            "masked_key": _mask(settings.openai_api_key),
            "chat_model": settings.openai_model,
            "embedding_model": settings.openai_embedding_model,
        },
        "groq": {
            "configured": bool(settings.groq_api_key),
            "masked_key": _mask(settings.groq_api_key),
            "model": settings.groq_model,
            "role": "fallback LLM provider",
        },
        "redis": {
            "configured": bool(settings.redis_url),
            "note": (
                None
                if settings.redis_url
                else "Not wired into any code path yet — rate limiting and the ingestion "
                "queue currently run in-process (see app/rate_limit.py)."
            ),
        },
    }


async def get_system_status(db: AsyncSession) -> dict:
    settings = get_settings()
    db_ok = await _database_reachable(db)

    checks = {
        "database": "ok" if db_ok else "unreachable",
        "embedding_provider": "configured" if settings.openai_api_key else "not_configured",
        "llm_primary_openai": "configured" if settings.openai_api_key else "not_configured",
        "llm_fallback_groq": "configured" if settings.groq_api_key else "not_configured",
        "redis": "configured" if settings.redis_url else "not_configured",
    }
    # Only the database is load-bearing for the app to function at all —
    # missing LLM/Redis config is a real but non-fatal degradation, already
    # surfaced per-check above rather than folded into one boolean.
    overall = "healthy" if db_ok else "degraded"

    return {"overall": overall, "checks": checks}
