"""Phase 9: inbound voice calls (global, no India voice stack)

Revision ID: 0030
Revises: 0029
Create Date: 2026-07-24

Adds 'voice' to conversations.channel (the transcript itself reuses the
existing conversations/messages tables — see app.voice.constants' module
docstring for why this is deliberate, not an oversight) and a new
voice_calls table for call-specific metadata that doesn't belong on either.
RLS follows the established single-resort pattern (0009/.../0029).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_AUTHENTICATED = "auth.uid() IS NOT NULL"


def upgrade() -> None:
    op.execute("ALTER TABLE conversations DROP CONSTRAINT ck_conversations_channel")
    op.execute(
        "ALTER TABLE conversations ADD CONSTRAINT ck_conversations_channel "
        "CHECK (channel IN ('whatsapp', 'webchat', 'voice'))"
    )

    op.create_table(
        "voice_calls",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_id", pg.UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("twilio_call_sid", sa.String(64), nullable=True, unique=True),
        sa.Column("livekit_room_name", sa.String(128), nullable=True),
        sa.Column("from_number", sa.String(30), nullable=True),
        sa.Column("to_number", sa.String(30), nullable=True),
        sa.Column("direction", sa.String(10), nullable=False, server_default="inbound"),
        sa.Column("status", sa.String(20), nullable=False, server_default="ringing"),
        sa.Column("outcome", sa.String(20), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('ringing', 'in_progress', 'completed', 'failed', 'no_answer')", name="ck_voice_calls_status"
        ),
        sa.CheckConstraint("direction IN ('inbound')", name="ck_voice_calls_direction"),
        sa.CheckConstraint(
            "outcome IS NULL OR outcome IN ('ai_handled', 'escalated', 'staff_handled', 'failed', 'abandoned')",
            name="ck_voice_calls_outcome",
        ),
    )
    op.create_index("ix_voice_calls_conversation_id", "voice_calls", ["conversation_id"])
    op.create_index("ix_voice_calls_twilio_call_sid", "voice_calls", ["twilio_call_sid"])
    op.create_index("ix_voice_calls_status", "voice_calls", ["status"])

    op.execute("ALTER TABLE voice_calls ENABLE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY voice_calls_select ON voice_calls FOR SELECT USING (" + _AUTHENTICATED + ")")
    op.execute(
        "CREATE POLICY voice_calls_modify ON voice_calls FOR ALL "
        "USING (" + _AUTHENTICATED + ") WITH CHECK (" + _AUTHENTICATED + ")"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS voice_calls_modify ON voice_calls")
    op.execute("DROP POLICY IF EXISTS voice_calls_select ON voice_calls")
    op.drop_index("ix_voice_calls_status", table_name="voice_calls")
    op.drop_index("ix_voice_calls_twilio_call_sid", table_name="voice_calls")
    op.drop_index("ix_voice_calls_conversation_id", table_name="voice_calls")
    op.drop_table("voice_calls")

    op.execute("ALTER TABLE conversations DROP CONSTRAINT ck_conversations_channel")
    op.execute(
        "ALTER TABLE conversations ADD CONSTRAINT ck_conversations_channel "
        "CHECK (channel IN ('whatsapp', 'webchat'))"
    )
