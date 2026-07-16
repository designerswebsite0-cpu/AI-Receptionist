import uuid

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_audit_event
from app.auth import service
from app.auth.jwt import verify_access_token
from app.auth.schemas import LoginRequest, RefreshRequest
from app.common.responses import success
from app.database import get_db
from app.deps import get_current_user
from app.errors import UnauthorizedError
from app.rate_limit import enforce_rate_limit
from app.resort.repository import get_resort_settings
from app.users.models import User
from app.users.service import upsert_user_from_identity

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login")
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    enforce_rate_limit(request)
    tokens = await service.login(body.email, body.password)

    identity = verify_access_token(tokens["access_token"])
    await upsert_user_from_identity(db, identity)
    await record_audit_event(
        db,
        actor_user_id=uuid.UUID(identity.user_id),
        action="auth.login",
        resource_type="user",
        resource_id=identity.user_id,
        metadata={},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    return success(
        {
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "expires_in": tokens.get("expires_in", 3600),
            "token_type": "bearer",
        }
    )


@router.post("/refresh")
async def refresh(body: RefreshRequest) -> dict:
    tokens = await service.refresh(body.refresh_token)
    return success(
        {
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "expires_in": tokens.get("expires_in", 3600),
            "token_type": "bearer",
        }
    )


@router.post("/logout")
async def logout(
    request: Request,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("Missing or malformed Authorization header")
    token = authorization.split(" ", 1)[1]
    identity = verify_access_token(token)

    await service.logout(token)
    await record_audit_event(
        db,
        actor_user_id=uuid.UUID(identity.user_id),
        action="auth.logout",
        resource_type="user",
        resource_id=identity.user_id,
        metadata={},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    return success({"logged_out": True})


@router.get("/me")
async def me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    """No memberships/roles anymore (single-resort refactor) — a verified
    session is sufficient for full access. `resort_configured` tells the
    dashboard whether to show first-run resort setup or the normal
    dashboard, without a second round trip.
    """
    resort_settings = await get_resort_settings(db)
    return success(
        {
            "user_id": str(user.id),
            "email": user.email,
            "resort_configured": resort_settings is not None,
        }
    )
