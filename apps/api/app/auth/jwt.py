from dataclasses import dataclass
from functools import lru_cache

import jwt
from jwt import PyJWKClient

from app.config import get_settings
from app.errors import UnauthorizedError

settings = get_settings()

# PyJWKClient caches fetched keys in-memory and only re-fetches the JWKS
# document when it encounters a kid it doesn't recognize (bounded by
# lifespan below). A Redis-backed shared cache is a documented Phase 3+
# follow-up once Upstash is wired — see docs/product_decisions.md.
_JWKS_CACHE_LIFESPAN_SECONDS = 3600


@lru_cache
def _jwk_client() -> PyJWKClient:
    return PyJWKClient(settings.supabase_jwks_url, lifespan=_JWKS_CACHE_LIFESPAN_SECONDS)


@dataclass(frozen=True)
class VerifiedIdentity:
    user_id: str
    email: str | None
    claims: dict


def verify_access_token(token: str) -> VerifiedIdentity:
    """Verify a Supabase-issued JWT against the project's published JWKS.

    Raises UnauthorizedError for any expired, malformed, or otherwise
    untrusted token. Never trust claims from a token that fails verification.
    """
    try:
        signing_key = _jwk_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience=settings.supabase_jwt_aud,
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Access token has expired") from exc
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Access token is invalid") from exc

    subject = claims.get("sub")
    if not subject:
        raise UnauthorizedError("Access token is missing a subject")

    return VerifiedIdentity(user_id=subject, email=claims.get("email"), claims=claims)
