import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import VerifiedIdentity
from app.users.models import User


async def upsert_user_from_identity(db: AsyncSession, identity: VerifiedIdentity) -> User:
    """Ensures a `users` profile row exists for a verified Supabase identity.

    Must run at login time (auth.router.login), before anything tries to
    reference this row via a foreign key (e.g. audit_logs.actor_user_id) —
    it cannot wait for the lazier upsert-on-read in app.deps.get_current_user,
    since that dependency isn't on the login path at all.
    """
    user = await db.get(User, uuid.UUID(identity.user_id))
    if user is None:
        user = User(id=uuid.UUID(identity.user_id), email=identity.email or f"{identity.user_id}@unknown.local")
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user
