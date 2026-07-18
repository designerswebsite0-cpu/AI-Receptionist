from datetime import UTC, datetime

from fastapi import Cookie, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.errors import UnauthorizedError
from app.webchat import repository
from app.webchat.constants import SESSION_COOKIE_NAME, SESSION_HEADER_NAME
from app.webchat.models import WebchatSession


async def get_webchat_session(
    db: AsyncSession = Depends(get_db),
    cookie_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    header_token: str | None = Header(default=None, alias=SESSION_HEADER_NAME),
) -> WebchatSession:
    """Resolves identity from the opaque token only — never from a
    client-supplied session_id/conversation_id/customer_id path or body
    value (brief §3: "Do not trust browser-provided customer IDs. Resolve
    database ownership server-side."). The header takes priority over the
    cookie: the intended integration shape is the website's own Next.js
    server holding the raw token and forwarding it server-to-server via
    this header, with the cookie path kept for a same-origin deployment
    that talks to this API directly.
    """
    token = header_token or cookie_token
    if not token:
        raise UnauthorizedError("Missing webchat session token")

    session = await repository.get_by_token_hash(db, repository.hash_token(token))
    if session is None:
        raise UnauthorizedError("Invalid or expired webchat session")
    if session.revoked_at is not None:
        raise UnauthorizedError("This session has ended")

    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at < datetime.now(UTC):
        raise UnauthorizedError("This session has expired")

    repository.touch(session)
    await db.commit()
    return session
