"""Single-resort RLS policies

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-16

Replaces the tenant-membership-subquery RLS policies removed in 0008.
There is only one resort's data in this database now, so the only
question RLS needs to answer per table is "is the caller an authenticated
application user at all" — no membership lookup required. The FastAPI
backend (service_role, bypasses RLS) remains the primary authorization
gate; these policies are defense-in-depth for any direct-Postgres access
path (Supabase Realtime, future connectors), same rationale as the
tenant-scoped policies they replace — see architecture.md §12.

audit_logs gets SELECT only (no INSERT/UPDATE/DELETE policy at all): audit
rows are written exclusively by the backend's service_role connection, and
must not be publicly writable — rules.md.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_AUTHENTICATED = "auth.uid() IS NOT NULL"

# Tables where authenticated users may read and write via RLS (defense in
# depth only — the backend enforces the real rules).
_READ_WRITE_TABLES = [
    "users",
    "customers",
    "customer_contacts",
    "customer_notes",
    "customer_tags",
    "conversations",
    "conversation_state_events",
    "messages",
    "message_attachments",
    "resort_settings",
]


def upgrade() -> None:
    # resort_settings is new as of migration 0007 and never had RLS enabled.
    # Every other table in _READ_WRITE_TABLES already has RLS enabled from
    # migrations 0002/0006 — dropping their old policies in 0008 removed
    # the policies, not the enabled flag.
    op.execute("ALTER TABLE resort_settings ENABLE ROW LEVEL SECURITY")

    for table in _READ_WRITE_TABLES:
        op.execute(
            f"""
            CREATE POLICY {table}_select ON {table} FOR SELECT
            USING ({_AUTHENTICATED})
            """
        )
        op.execute(
            f"""
            CREATE POLICY {table}_modify ON {table} FOR ALL
            USING ({_AUTHENTICATED})
            WITH CHECK ({_AUTHENTICATED})
            """
        )

    # Audit logs: readable by any authenticated user, never directly
    # writable — the backend's service_role connection bypasses RLS to
    # insert these, so no INSERT/UPDATE/DELETE policy is created at all.
    op.execute(
        f"""
        CREATE POLICY audit_logs_select ON audit_logs FOR SELECT
        USING ({_AUTHENTICATED})
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS audit_logs_select ON audit_logs")
    for table in reversed(_READ_WRITE_TABLES):
        op.execute(f"DROP POLICY IF EXISTS {table}_modify ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_select ON {table}")
