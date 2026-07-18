"""Phase 5: webchat_sessions

Revision ID: 0024
Revises: 0023
Create Date: 2026-07-18

Anonymous website-guest session identity. Never stores the raw opaque
session token — only its SHA-256 hash, so a leaked database row can't be
replayed as a live session (same principle as a password hash). The raw
token lives only in the guest's browser cookie and is hashed on every
request before lookup — see docs/phase-5/WEBCHAT_SECURITY.md.

RLS follows the established single-resort pattern (0009/0019/0023): the
FastAPI backend's service_role connection bypasses RLS entirely and is the
real authorization gate (it resolves a session by hashing the guest's
cookie token, never by trusting a client-supplied id). The
`auth.uid() IS NOT NULL` policy here is defense-in-depth for any direct
Postgres/PostgREST access path — since anonymous guests never hold a
Supabase auth session, this correctly means the table is unreadable via
that path by anyone but the backend itself.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_AUTHENTICATED = "auth.uid() IS NOT NULL"


def upgrade() -> None:
    op.create_table(
        "webchat_sessions",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column(
            "customer_id", pg.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "conversation_id", pg.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("session_metadata", pg.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
            onupdate=sa.func.now(), nullable=False,
        ),
    )
    op.create_index("ix_webchat_sessions_token_hash", "webchat_sessions", ["token_hash"], unique=True)
    op.create_index("ix_webchat_sessions_customer_id", "webchat_sessions", ["customer_id"])
    op.create_index("ix_webchat_sessions_conversation_id", "webchat_sessions", ["conversation_id"])
    op.create_index("ix_webchat_sessions_expires_at", "webchat_sessions", ["expires_at"])

    op.execute("ALTER TABLE webchat_sessions ENABLE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY webchat_sessions_select ON webchat_sessions FOR SELECT USING (" + _AUTHENTICATED + ")")
    op.execute(
        "CREATE POLICY webchat_sessions_modify ON webchat_sessions FOR ALL "
        "USING (" + _AUTHENTICATED + ") WITH CHECK (" + _AUTHENTICATED + ")"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS webchat_sessions_modify ON webchat_sessions")
    op.execute("DROP POLICY IF EXISTS webchat_sessions_select ON webchat_sessions")
    op.drop_index("ix_webchat_sessions_expires_at", table_name="webchat_sessions")
    op.drop_index("ix_webchat_sessions_conversation_id", table_name="webchat_sessions")
    op.drop_index("ix_webchat_sessions_customer_id", table_name="webchat_sessions")
    op.drop_index("ix_webchat_sessions_token_hash", table_name="webchat_sessions")
    op.drop_table("webchat_sessions")
