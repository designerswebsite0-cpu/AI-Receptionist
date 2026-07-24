from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# One .env at the repo root serves every app (requirements.md §13) in local
# dev, resolved from this file's own location rather than the process CWD,
# since uvicorn is typically launched from apps/api/ — a CWD-relative
# "./.env" would silently miss the real file and fall back to defaults/
# errors instead. The Docker image (Dockerfile: COPY app ./app) flattens
# this to /app/app/config.py, one directory shallower than the monorepo
# checkout's apps/api/app/config.py — parents[3] doesn't exist there, and
# indexing it unconditionally crashed the container before Settings could
# even load (real environment variables, e.g. Railway's, still work fine
# without a file — this lookup is a local-dev convenience, not a
# requirement). Falls back to None (no env file) when running that shallow.
_REPO_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env" if len(Path(__file__).resolve().parents) > 3 else None


class Settings(BaseSettings):
    """Central environment configuration. Fails fast on missing required values."""

    model_config = SettingsConfigDict(
        env_file=str(_REPO_ROOT_ENV) if _REPO_ROOT_ENV else None,
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

    # Redis (optional — used by the Phase 3 ingestion queue when set,
    # falls back to an in-request InlineIngestionQueue otherwise)
    redis_url: str | None = None

    # Phase 3: Knowledge Intelligence Engine
    openai_api_key: str | None = None
    openai_embedding_model: str = "text-embedding-3-large"
    knowledge_storage_bucket: str = "knowledge-documents"
    clamav_host: str = "localhost"
    clamav_port: int = 3310
    clamav_required_in_production: bool = True
    tesseract_cmd: str | None = None  # override PATH lookup if needed

    # Phase 4: AI Orchestration — OpenAI primary, Groq fallback per
    # architecture.md §4.4 ("Call OpenAI as the primary provider. Use Groq
    # according to explicit fallback policy.")
    openai_model: str = "gpt-4o-mini"
    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    orchestration_max_context_tokens: int = 4000
    # Caps the model's OUTPUT length — guests expect short, chat-like
    # replies (a real front-desk chat message, not an essay), and every
    # completion token costs money and adds latency regardless of whether
    # the guest wanted that much detail. ~220 tokens is roughly 2-4 short
    # sentences to a brief paragraph.
    orchestration_max_response_tokens: int = 220
    orchestration_provider_failure_threshold: int = 3
    orchestration_provider_cooldown_seconds: int = 60

    # Phase 5: Website Chat Channel — public, anonymous-guest surface.
    # Limits are read from here (not hard-coded in the router) so ops can
    # tune them per deployment without a code change.
    webchat_enabled: bool = True
    webchat_allowed_origins: str = "http://localhost:3000"
    # 90 days rather than the original 7 — a guest researching a stay
    # commonly returns days or weeks later; the session cookie (and thus
    # "am I talking to the same returning guest") should comfortably
    # outlive that gap. Contact-based dedup (app.webchat.service
    # capture_contact) still covers the cross-device/cleared-cookie case
    # on top of this.
    webchat_session_ttl_seconds: int = 60 * 60 * 24 * 90  # 90 days
    webchat_max_message_length: int = 2000
    webchat_rate_limit_per_minute: int = 8  # messages, per session
    webchat_conversation_limit_per_ip_per_hour: int = 5  # new sessions, per IP
    webchat_message_limit_per_ip_per_minute: int = 20  # burst guard across sessions, per IP

    # Monitoring (optional)
    sentry_dsn: str | None = None
    better_stack_token: str | None = None
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None

    # Phase 7: Room Booking — SMS confirmation. All three must be set for a
    # real send; when any is missing, app.bookings.sms logs and marks the
    # booking's confirmation_sms_status "skipped_not_configured" instead of
    # raising, since staff must still be able to confirm a booking in the
    # dashboard even before Twilio is fully provisioned.
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from_number: str | None = None
    # Rolling window, not calendar-year-bound (a guest in December asking
    # about next January must still be within range) — see the 2026-07-24
    # booking-rooms brief.
    booking_max_advance_days: int = 183

    # Phase 9: Global Voice Call System (inbound only). No production
    # credentials exist yet for any of these — every field is optional and
    # every voice code path must degrade gracefully (never crash app
    # startup, never break other channels) when unset. See
    # docs/phase-9/ENVIRONMENT.md for what each value is and where to get
    # it once real accounts exist.
    voice_enabled: bool = False
    # A separate field from twilio_from_number (Phase 7 SMS) — voice and SMS
    # may end up on different Twilio numbers, and conflating them would make
    # it impossible to reason about which number does what.
    twilio_phone_number: str | None = None

    livekit_url: str | None = None
    livekit_api_key: str | None = None
    livekit_api_secret: str | None = None

    deepgram_api_key: str | None = None

    elevenlabs_api_key: str | None = None
    elevenlabs_voice_id: str | None = None

    # Voice-specific LLM ordering is the REVERSE of webchat's (architecture.md
    # §4.4 has OpenAI primary / Groq fallback for text channels) — the
    # Phase 9 brief explicitly specifies Groq primary / OpenAI 4o-mini
    # fallback for voice, presumably for Groq's lower inference latency,
    # which matters far more for a live phone call than for chat. Reuses
    # the same groq_api_key/groq_model/openai_api_key/openai_model settings
    # above; this is purely an ordering flag read by app.voice.agent.
    voice_primary_provider: str = "groq"

    # Safety caps — never let a single call, or a stuck agent, run forever
    # even if a provider hangs instead of erroring.
    voice_max_call_duration_seconds: int = 60 * 30  # 30 minutes
    voice_silence_timeout_seconds: int = 30

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
    def webchat_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.webchat_allowed_origins.split(",") if origin.strip()]

    @property
    def supabase_jwks_url(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"

    @property
    def supabase_gotrue_url(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1"

    @property
    def supabase_storage_url(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/storage/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
