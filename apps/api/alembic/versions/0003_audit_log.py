"""audit_logs

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MEMBERSHIP_SUBQUERY = """
    SELECT tenant_id FROM tenant_members
    WHERE user_id = auth.uid() AND status = 'active' AND deleted_at IS NULL
"""


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", pg.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "actor_user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.String(100), nullable=True),
        sa.Column("event_metadata", pg.JSONB, nullable=False, server_default="{}"),
        sa.Column("ip_address", pg.INET, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])

    # Audit logs are written exclusively by the backend (service_role,
    # bypasses RLS). This policy only governs hypothetical direct reads —
    # e.g. a future "security events" dashboard panel using Supabase
    # Realtime/PostgREST directly — and intentionally has no INSERT/UPDATE/
    # DELETE policy, so direct client writes are always rejected.
    op.execute("ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY audit_logs_select ON audit_logs FOR SELECT
        USING (tenant_id IN ({_MEMBERSHIP_SUBQUERY}))
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS audit_logs_select ON audit_logs")
    op.drop_table("audit_logs")
