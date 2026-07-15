import httpx

from app.config import get_settings
from app.errors import UnauthorizedError
from app.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

# Auth is proxied through our backend (rather than every client calling
# Supabase GoTrue directly) so the dashboard, widget, and future voice-agent
# share one auth surface and one audit trail — see docs/product_decisions.md.


def _gotrue_headers() -> dict:
    return {"apikey": settings.supabase_anon_key, "Content-Type": "application/json"}


async def login(email: str, password: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{settings.supabase_gotrue_url}/token",
            params={"grant_type": "password"},
            headers=_gotrue_headers(),
            json={"email": email, "password": password},
        )
    if response.status_code != 200:
        logger.warning("login_failed", extra={"status_code": response.status_code})
        raise UnauthorizedError("Invalid email or password")
    return response.json()


async def refresh(refresh_token: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{settings.supabase_gotrue_url}/token",
            params={"grant_type": "refresh_token"},
            headers=_gotrue_headers(),
            json={"refresh_token": refresh_token},
        )
    if response.status_code != 200:
        raise UnauthorizedError("Refresh token is invalid or expired")
    return response.json()


async def logout(access_token: str) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{settings.supabase_gotrue_url}/logout",
            headers={**_gotrue_headers(), "Authorization": f"Bearer {access_token}"},
        )
    # GoTrue returns 204 on success; a failure here is non-fatal for the
    # caller (the session will simply expire) but is still surfaced.
    if response.status_code not in (204, 200):
        logger.warning("logout_upstream_error", extra={"status_code": response.status_code})
