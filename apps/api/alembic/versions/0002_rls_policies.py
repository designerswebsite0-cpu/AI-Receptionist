"""Row Level Security policies for tenant-owned tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-14

Defense-in-depth: the FastAPI backend is the primary authorization gate
(see app.deps.get_current_membership / app.roles.permissions) using the
Supabase service_role connection, which bypasses RLS by design. These
policies exist so that ANY direct Postgres access — Supabase Realtime
subscriptions (Phase 2+), ad-hoc dashboard queries, future connectors —
can never cross a tenant boundary even if application-layer checks are
ever bypassed or misconfigured. See architecture.md §12 and rules.md §5.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MEMBERSHIP_SUBQUERY = """
    SELECT tenant_id FROM tenant_members
    WHERE user_id = auth.uid() AND status = 'active' AND deleted_at IS NULL
"""

def upgrade() -> None:
    op.execute("ALTER TABLE tenants ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenants_select ON tenants FOR SELECT
        USING (id IN ({_MEMBERSHIP_SUBQUERY}))
        """
    )
    op.execute(
        f"""
        CREATE POLICY tenants_update ON tenants FOR UPDATE
        USING (id IN ({_MEMBERSHIP_SUBQUERY}))
        WITH CHECK (id IN ({_MEMBERSHIP_SUBQUERY}))
        """
    )
    op.execute(
        "CREATE POLICY tenants_insert ON tenants FOR INSERT WITH CHECK (auth.uid() IS NOT NULL)"
    )

    op.execute("ALTER TABLE tenant_settings ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_settings_select ON tenant_settings FOR SELECT
        USING (tenant_id IN ({_MEMBERSHIP_SUBQUERY}))
        """
    )
    op.execute(
        f"""
        CREATE POLICY tenant_settings_update ON tenant_settings FOR UPDATE
        USING (tenant_id IN ({_MEMBERSHIP_SUBQUERY}))
        WITH CHECK (tenant_id IN ({_MEMBERSHIP_SUBQUERY}))
        """
    )

    op.execute("ALTER TABLE tenant_members ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_members_select ON tenant_members FOR SELECT
        USING (tenant_id IN ({_MEMBERSHIP_SUBQUERY}))
        """
    )
    op.execute(
        f"""
        CREATE POLICY tenant_members_modify ON tenant_members FOR ALL
        USING (tenant_id IN ({_MEMBERSHIP_SUBQUERY}))
        WITH CHECK (tenant_id IN ({_MEMBERSHIP_SUBQUERY}))
        """
    )

    op.execute("ALTER TABLE tenant_roles ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_roles_select ON tenant_roles FOR SELECT
        USING (tenant_id IS NULL OR tenant_id IN ({_MEMBERSHIP_SUBQUERY}))
        """
    )

    op.execute("ALTER TABLE tenant_permissions ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_permissions_select ON tenant_permissions FOR SELECT
        USING (
            role_id IN (
                SELECT id FROM tenant_roles
                WHERE tenant_id IS NULL OR tenant_id IN ({_MEMBERSHIP_SUBQUERY})
            )
        )
        """
    )

    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY users_select ON users FOR SELECT
        USING (
            id = auth.uid()
            OR id IN (
                SELECT user_id FROM tenant_members
                WHERE status = 'active' AND deleted_at IS NULL
                AND tenant_id IN ({_MEMBERSHIP_SUBQUERY})
            )
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS users_select ON users")
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")

    op.execute("DROP POLICY IF EXISTS tenant_permissions_select ON tenant_permissions")
    op.execute("ALTER TABLE tenant_permissions DISABLE ROW LEVEL SECURITY")

    op.execute("DROP POLICY IF EXISTS tenant_roles_select ON tenant_roles")
    op.execute("ALTER TABLE tenant_roles DISABLE ROW LEVEL SECURITY")

    op.execute("DROP POLICY IF EXISTS tenant_members_modify ON tenant_members")
    op.execute("DROP POLICY IF EXISTS tenant_members_select ON tenant_members")
    op.execute("ALTER TABLE tenant_members DISABLE ROW LEVEL SECURITY")

    op.execute("DROP POLICY IF EXISTS tenant_settings_update ON tenant_settings")
    op.execute("DROP POLICY IF EXISTS tenant_settings_select ON tenant_settings")
    op.execute("ALTER TABLE tenant_settings DISABLE ROW LEVEL SECURITY")

    op.execute("DROP POLICY IF EXISTS tenants_insert ON tenants")
    op.execute("DROP POLICY IF EXISTS tenants_update ON tenants")
    op.execute("DROP POLICY IF EXISTS tenants_select ON tenants")
    op.execute("ALTER TABLE tenants DISABLE ROW LEVEL SECURITY")
