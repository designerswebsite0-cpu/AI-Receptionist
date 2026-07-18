"""Phase 4: RLS for orchestration tables

Revision ID: 0023
Revises: 0022
Create Date: 2026-07-18

Same defense-in-depth pattern as 0009/0019 — authenticated-user policies,
not a guest/staff distinction (there is none in this single-resort
deployment). The real guest-safety boundary for what an AI response may
say is enforced upstream, in app.knowledge.retrieval (visibility/
retrieval_enabled/status/expiry filtering) — these tables only ever store
already-filtered citations and internal decision traces, never raw
unfiltered content.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_AUTHENTICATED = "auth.uid() IS NOT NULL"
_TABLES = ["orchestration_turns", "service_requests"]


def upgrade() -> None:
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY {table}_select ON {table} FOR SELECT USING ({_AUTHENTICATED})")
        op.execute(
            f"CREATE POLICY {table}_modify ON {table} FOR ALL "
            f"USING ({_AUTHENTICATED}) WITH CHECK ({_AUTHENTICATED})"
        )


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"DROP POLICY IF EXISTS {table}_modify ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_select ON {table}")
