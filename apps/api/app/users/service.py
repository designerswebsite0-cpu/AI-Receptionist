import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import VerifiedIdentity
from app.errors import NotFoundError
from app.users.models import User
from app.users.schemas import UserUpdateRequest


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


async def mark_login(db: AsyncSession, user: User) -> None:
    """Stamps last_login_at for the Staff Management roster. Called
    alongside upsert_user_from_identity on every successful login — a
    separate function (rather than folded into the upsert) since the
    upsert also runs on the lazier get_current_user path, where "logged
    in just now" isn't actually true."""
    user.last_login_at = datetime.now(UTC)


async def get_user_or_404(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise NotFoundError("Staff user not found")
    return user


async def update_user(db: AsyncSession, *, user_id: uuid.UUID, body: UserUpdateRequest) -> User:
    user = await get_user_or_404(db, user_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return user
