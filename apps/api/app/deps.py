from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import VerifiedIdentity, verify_access_token
from app.database import get_db
from app.errors import UnauthorizedError
from app.logging import user_id_var
from app.users.models import User
from app.users.service import upsert_user_from_identity


async def get_verified_identity(authorization: str | None = Header(default=None)) -> VerifiedIdentity:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("Missing or malformed Authorization header")
    token = authorization.split(" ", 1)[1]
    identity = verify_access_token(token)
    user_id_var.set(identity.user_id)
    return identity


async def get_current_user(
    identity: VerifiedIdentity = Depends(get_verified_identity),
    db: AsyncSession = Depends(get_db),
) -> User:
    """The only access-control dependency this deployment needs: a valid
    Supabase session. Per product_decisions.md (single-resort refactor),
    there is no tenant/role concept left — any authenticated user has full
    access to this deployment's single resort.
    """
    return await upsert_user_from_identity(db, identity)
