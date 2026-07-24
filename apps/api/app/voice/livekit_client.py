"""Thin wrapper over LiveKit's server SDK (livekit.api) — token minting for
staff takeover, best-effort room teardown for staff-initiated call end, and
webhook signature verification. Every function degrades gracefully to a
clearly-labeled no-op when LiveKit isn't configured (no LIVEKIT_URL/
API_KEY/API_SECRET yet), never raising into a caller that just wants to
know "is this available".
"""

from livekit import api

from app.config import get_settings
from app.logging import get_logger

logger = get_logger(__name__)


def is_configured() -> bool:
    settings = get_settings()
    return bool(settings.livekit_url and settings.livekit_api_key and settings.livekit_api_secret)


def mint_staff_token(*, room_name: str, staff_user_id: str, staff_name: str | None) -> str | None:
    """Grants a staff browser (via livekit-client, joining the same room as
    the caller) publish+subscribe access so their mic streams directly into
    the live call — the actual join happens client-side; this only proves
    the staff member is authorized for that specific room."""
    settings = get_settings()
    if not is_configured():
        return None

    token = (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(f"staff-{staff_user_id}")
        .with_name(staff_name or "Staff")
        .with_grants(api.VideoGrants(room_join=True, room=room_name, can_publish=True, can_subscribe=True))
    )
    return token.to_jwt()


async def end_room(room_name: str) -> bool:
    """Best-effort — a staff "End call" action should never crash even if
    LiveKit is unreachable or the room already ended on its own."""
    settings = get_settings()
    if not is_configured():
        return False

    client = api.LiveKitAPI(settings.livekit_url, settings.livekit_api_key, settings.livekit_api_secret)
    try:
        await client.room.delete_room(api.DeleteRoomRequest(room=room_name))
        return True
    except Exception:
        logger.exception("livekit_end_room_failed", extra={"room_name": room_name})
        return False
    finally:
        await client.aclose()


def verify_webhook(*, body: str, auth_header: str) -> "api.WebhookEvent | None":
    settings = get_settings()
    if not is_configured():
        return None
    try:
        receiver = api.WebhookReceiver(api.TokenVerifier(settings.livekit_api_key, settings.livekit_api_secret))
        return receiver.receive(body, auth_header)
    except Exception:
        logger.warning("livekit_webhook_verification_failed")
        return None
