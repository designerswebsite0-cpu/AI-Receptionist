from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# One .env at the repo root serves every app (requirements.md §13). Resolved
# from this file's own location rather than the process CWD, since uvicorn
# is typically launched from apps/api/ — a CWD-relative "./.env" would
# silently miss the real file and fall back to defaults/errors instead.
_REPO_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    """Central environment configuration. Fails fast on missing required values."""

    model_config = SettingsConfigDict(
        env_file=str(_REPO_ROOT_ENV),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_env: Literal["development", "staging", "production", "test"] = "development"
    app_name: str = "ai-receptionist-api"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_allowed_origins: str = "http://localhost:3000"

    # Database
    database_url: str = Field(..., description="Async SQLAlchemy URL (postgresql+asyncpg://...)")
    # Optional: a direct (non-pooled) connection string for Alembic. Prefer
    # this over deriving from database_url when the app connects through a
    # transaction-mode pooler (e.g. Supabase's port 6543), since DDL and
    # Alembic's session handling don't play well with that pooling mode.
    database_url_sync: str | None = Field(
        default=None, description="Sync SQLAlchemy URL for Alembic (postgresql+psycopg2://...)"
    )

    # Supabase
    supabase_url: str = Field(..., description="https://<project>.supabase.co")
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_jwt_aud: str = "authenticated"

    # Security
    auth_login_rate_limit_per_minute: int = 10
    session_cookie_secure: bool = True

    # Temporary development-phase switch (see docs/product_decisions.md).
    # RBAC tables/roles/permissions stay fully implemented; when this is
    # False, permission checks are skipped so any active tenant member has
    # full access. Tenant membership/isolation is NEVER bypassed by this
    # flag — only fine-grained role permissions are. Flip to True to
    # re-enable enforcement once the AI/RAG/booking build-out is stable.
    rbac_enforcement_enabled: bool = False

    # Redis (optional until Phase 3)
    redis_url: str | None = None

    # Monitoring (optional)
    sentry_dsn: str | None = None
    better_stack_token: str | None = None
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None

    @field_validator("database_url")
    @classmethod
    def _require_asyncpg_driver(cls, value: str) -> str:
        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use the postgresql+asyncpg:// driver")
        return value

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @property
    def supabase_jwks_url(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"

    @property
    def supabase_gotrue_url(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
