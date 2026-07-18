import hashlib
import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.webchat.constants import TOKEN_BYTES
from app.webchat.models import WebchatSession


def generate_token() -> str:
    """A fresh high-entropy opaque token — never a sequential/database id
    (brief §3). Returned to the caller exactly once, at session creation."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
    """SHA-256 of the raw token — this, not the token itself, is what's
    persisted. A leaked database row can't be replayed as a live session,
    same principle as storing a password hash instead of the password."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def create_session(
    db: AsyncSession,
    *,
    customer_id: uuid.UUID,
    conversation_id: uuid.UUID,
    token_hash: str,
    expires_at: datetime,
) -> WebchatSession:
    session = WebchatSession(
        customer_id=customer_id,
        conversation_id=conversation_id,
        token_hash=token_hash,
        last_seen_at=datetime.now(UTC),
        expires_at=expires_at,
    )
    db.add(session)
    await db.flush()
    return session


async def get_by_token_hash(db: AsyncSession, token_hash: str) -> WebchatSession | None:
    result = await db.execute(select(WebchatSession).where(WebchatSession.token_hash == token_hash))
    return result.scalar_one_or_none()


async def get_by_id(db: AsyncSession, session_id: uuid.UUID) -> WebchatSession | None:
    result = await db.execute(select(WebchatSession).where(WebchatSession.id == session_id))
    return result.scalar_one_or_none()


def touch(session: WebchatSession) -> None:
    session.last_seen_at = datetime.now(UTC)


def revoke(session: WebchatSession) -> None:
    session.revoked_at = datetime.now(UTC)
