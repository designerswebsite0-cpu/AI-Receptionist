"""Settings hub support (Phase X Stage 8): Integrations and System
Monitoring both read real configuration/connectivity only — never a
stack trace, an env var dump, or a fabricated "all systems operational"
banner. A masked API key fragment (first 4 + last 4 characters) is the
most any caller ever sees of a real secret; the raw value never leaves
app.config.Settings.
"""

from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog
from app.bookings.models import RoomBooking
from app.config import get_settings
from app.conversations.models import Conversation
from app.knowledge.models import KnowledgeSource
from app.notifications import repository as notifications_repository


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


async def _domain_signals(db: AsyncSession) -> dict:
    """Real, per-domain operational counts — not a synthetic 'health score'.
    Lets staff answer "is something wrong, and where" without grepping logs:
    each number here is a direct, unaggregated count from the same tables
    the rest of the dashboard reads."""
    last_24h = datetime.now(UTC) - timedelta(hours=24)

    kb_rows = (
        await db.execute(
            select(KnowledgeSource.processing_status, func.count()).group_by(KnowledgeSource.processing_status)
        )
    ).all()
    kb_counts = dict(kb_rows)
    kb_active = (
        await db.execute(
            select(func.count()).select_from(KnowledgeSource).where(KnowledgeSource.retrieval_enabled.is_(True))
        )
    ).scalar_one()

    escalated = (
        await db.execute(select(func.count()).select_from(Conversation).where(Conversation.status == "escalated"))
    ).scalar_one()
    # A conversation neither the AI nor a staff member currently owns —
    # this should never happen if handoff/release always fire correctly,
    # so a non-zero count here is itself a signal something upstream broke.
    orphaned = (
        await db.execute(
            select(func.count())
            .select_from(Conversation)
            .where(
                Conversation.ai_active.is_(False),
                Conversation.human_active.is_(False),
                Conversation.status != "closed",
            )
        )
    ).scalar_one()

    pending_bookings = (
        await db.execute(
            select(func.count()).select_from(RoomBooking).where(RoomBooking.status == "pending_review")
        )
    ).scalar_one()

    error_rows = (
        await db.execute(
            select(AuditLog.resource_type, func.count())
            .where(AuditLog.created_at >= last_24h, AuditLog.action.ilike("%fail%"))
            .group_by(AuditLog.resource_type)
            .order_by(func.count().desc())
        )
    ).all()

    unread_notifications = await notifications_repository.count_unread(db)

    return {
        "knowledge_base": {
            "active_sources": kb_active,
            "failed": kb_counts.get("failed", 0),
            "needs_review": kb_counts.get("needs_review", 0),
            "pending": kb_counts.get("pending", 0),
        },
        "conversations": {
            "escalated_needing_attention": escalated,
            "orphaned_not_handled_by_ai_or_staff": orphaned,
        },
        "bookings": {"pending_review": pending_bookings},
        "notifications": {"unread": unread_notifications},
        "recent_errors_24h": [{"area": area, "count": count} for area, count in error_rows],
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
    domains = await _domain_signals(db) if db_ok else None

    return {"overall": overall, "checks": checks, "domains": domains}
