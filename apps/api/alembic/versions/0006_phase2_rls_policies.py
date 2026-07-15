"""RLS policies for Phase 2 tables (customers, conversations, messages, ...)

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-16

Same defense-in-depth rationale as migration 0002: the FastAPI backend
(service_role, bypasses RLS) is the primary authorization gate via
app.deps.get_current_membership + app.roles.permissions.require_permission.
These policies protect any direct-Postgres access path.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MEMBERSHIP_SUBQUERY = """
    SELECT tenant_id FROM tenant_members
    WHERE user_id = auth.uid() AND status = 'active' AND deleted_at IS NULL
"""

# Every Phase 2 table carries its own tenant_id column (TenantScopedMixin),
# so one policy shape covers all of them uniformly.
_TENANT_SCOPED_TABLES = [
    "customers",
    "customer_contacts",
    "customer_notes",
    "customer_tags",
    "conversations",
    "conversation_state_events",
    "messages",
    "message_attachments",
]


def upgrade() -> None:
    for table in _TENANT_SCOPED_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_select ON {table} FOR SELECT
            USING (tenant_id IN ({_MEMBERSHIP_SUBQUERY}))
            """
        )
        op.execute(
            f"""
            CREATE POLICY {table}_modify ON {table} FOR ALL
            USING (tenant_id IN ({_MEMBERSHIP_SUBQUERY}))
            WITH CHECK (tenant_id IN ({_MEMBERSHIP_SUBQUERY}))
            """
        )


def downgrade() -> None:
    for table in reversed(_TENANT_SCOPED_TABLES):
        op.execute(f"DROP POLICY IF EXISTS {table}_modify ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_select ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
