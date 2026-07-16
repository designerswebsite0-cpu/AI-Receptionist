"""Remove multi-tenancy — Phase 2.5 single-resort architecture refactor

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-16

The product is no longer multi-tenant SaaS: each deployment now serves
exactly one resort with its own database (see docs/product_decisions.md).
This migration:

1. Drops every RLS policy that references tenant_id (they must go before
   the column/tables they depend on can be dropped).
2. Drops tenant_id (and tenant-scoped constraints/indexes) from every
   business table that still has it.
3. Restructures audit_logs: drops tenant_id, adds before_state/after_state/
   correlation_id (rules.md audit requirements, not tenant-related, bundled
   here since it's touching the same table anyway).
4. Drops the tenant system tables themselves: tenant_permissions,
   tenant_members, tenant_roles, tenant_settings, tenants (in dependency
   order — no CASCADE relied on, each table is dropped explicitly).

Data note: this database had exactly one real tenant ("Resorts") with one
member and zero customers/conversations/messages at the time of this
migration — verified by hand before writing this migration, not assumed.
There is nothing to preserve or re-attach; if a deployment somehow reaches
this migration with real customer/conversation data under multiple
tenants, that data is NOT tenant-disambiguated by this migration (there is
exactly one resort per database going forward, so multi-tenant data would
need manual review before running this — documented here rather than
silently merged).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tables that got a (select, modify) RLS policy pair in migration 0006,
# all referencing tenant_id.
_PHASE2_RLS_TABLES = [
    "customers",
    "customer_contacts",
    "customer_notes",
    "customer_tags",
    "conversations",
    "conversation_state_events",
    "messages",
    "message_attachments",
]

# tenant_id column + its actual index name, per table (verified against
# the live database rather than assumed from a naming pattern — one table
# doesn't follow the pattern, see conversation_state_events below).
_TENANT_ID_TABLES = [
    ("customers", "ix_customers_tenant_id"),
    ("customer_notes", "ix_customer_notes_tenant_id"),
    ("customer_tags", "ix_customer_tags_tenant_id"),
    ("conversations", "ix_conversations_tenant_id"),
    ("conversation_state_events", "ix_conv_state_events_tenant_id"),
    ("messages", "ix_messages_tenant_id"),
    ("message_attachments", "ix_message_attachments_tenant_id"),
]


def upgrade() -> None:
    # --- 1. Drop RLS policies that reference tenant_id or tenant_members -
    # Policies on tenants/tenant_settings/tenant_roles/tenant_permissions
    # reference tenant_members in their USING clause (the shared membership
    # subquery from migration 0002) even though they aren't defined ON
    # tenant_members — Postgres tracks that as a dependency, so these must
    # be dropped before tenant_members itself, not just before their own
    # table (which would happen automatically via DROP TABLE anyway).
    for table in _PHASE2_RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_modify ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_select ON {table}")
    op.execute("DROP POLICY IF EXISTS users_select ON users")
    op.execute("DROP POLICY IF EXISTS audit_logs_select ON audit_logs")
    op.execute("DROP POLICY IF EXISTS tenants_select ON tenants")
    op.execute("DROP POLICY IF EXISTS tenants_update ON tenants")
    op.execute("DROP POLICY IF EXISTS tenants_insert ON tenants")
    op.execute("DROP POLICY IF EXISTS tenant_settings_select ON tenant_settings")
    op.execute("DROP POLICY IF EXISTS tenant_settings_update ON tenant_settings")
    op.execute("DROP POLICY IF EXISTS tenant_roles_select ON tenant_roles")
    op.execute("DROP POLICY IF EXISTS tenant_permissions_select ON tenant_permissions")
    op.execute("DROP POLICY IF EXISTS tenant_members_select ON tenant_members")
    op.execute("DROP POLICY IF EXISTS tenant_members_modify ON tenant_members")

    # --- 2. Drop tenant_id from business tables --------------------------
    for table, index_name in _TENANT_ID_TABLES:
        op.drop_index(index_name, table_name=table)
        op.drop_column(table, "tenant_id")

    # customer_contacts: tenant-scoped unique constraint -> global unique
    op.drop_constraint("uq_customer_contacts_tenant_type_value", "customer_contacts", type_="unique")
    op.drop_index("ix_customer_contacts_tenant_id", table_name="customer_contacts")
    op.drop_column("customer_contacts", "tenant_id")
    op.create_unique_constraint(
        "uq_customer_contacts_type_value", "customer_contacts", ["contact_type", "value"]
    )

    # --- 3. Restructure audit_logs ---------------------------------------
    op.drop_index("ix_audit_logs_tenant_id", table_name="audit_logs")
    op.drop_column("audit_logs", "tenant_id")
    op.add_column("audit_logs", sa.Column("before_state", pg.JSONB, nullable=True))
    op.add_column("audit_logs", sa.Column("after_state", pg.JSONB, nullable=True))
    op.add_column("audit_logs", sa.Column("correlation_id", sa.String(64), nullable=True))
    op.create_index("ix_audit_logs_correlation_id", "audit_logs", ["correlation_id"])

    # --- 4. Drop the tenant system tables, in FK-safe order --------------
    op.drop_table("tenant_permissions")
    op.drop_table("tenant_members")
    op.drop_table("tenant_roles")
    op.drop_table("tenant_settings")
    op.drop_table("tenants")


def downgrade() -> None:
    raise NotImplementedError(
        "Downgrade is intentionally not supported: reconstructing the "
        "multi-tenant schema would require re-inventing tenant_id "
        "ownership for rows created after this migration ran, which "
        "cannot be inferred. Restore from a pre-migration backup instead."
    )
