"""tenants, users, roles/permissions, tenant_members

Revision ID: 0001
Revises:
Create Date: 2026-07-14
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"])

    op.create_table(
        "users",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("full_name", sa.String(200), nullable=True),
        sa.Column("avatar_url", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "tenant_settings",
        sa.Column(
            "tenant_id", pg.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("default_language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("settings", pg.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "tenant_roles",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("description", sa.String(300), nullable=True),
        sa.Column("is_system", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("tenant_id", "name", name="uq_tenant_roles_tenant_name"),
    )
    op.create_index("ix_tenant_roles_tenant_id", "tenant_roles", ["tenant_id"])

    op.create_table(
        "tenant_permissions",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "role_id", pg.UUID(as_uuid=True), sa.ForeignKey("tenant_roles.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("permission_key", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("role_id", "permission_key", name="uq_role_permission"),
    )
    op.create_index("ix_tenant_permissions_role_id", "tenant_permissions", ["role_id"])
    op.create_index("ix_tenant_permissions_permission_key", "tenant_permissions", ["permission_key"])

    op.create_table(
        "tenant_members",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "role_id", pg.UUID(as_uuid=True), sa.ForeignKey("tenant_roles.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("invited_by", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_tenant_members_tenant_user"),
    )
    op.create_index("ix_tenant_members_tenant_id", "tenant_members", ["tenant_id"])
    op.create_index("ix_tenant_members_user_id", "tenant_members", ["user_id"])
    op.create_index("ix_tenant_members_role_id", "tenant_members", ["role_id"])

    _seed_system_roles_and_permissions()


def _seed_system_roles_and_permissions() -> None:
    # Data frozen at migration-authoring time on purpose — migrations must
    # stay reproducible even if app.roles.seed_data changes later. Keep this
    # in sync with app/roles/seed_data.py::SYSTEM_ROLES when that changes.
    system_roles = {
        "owner": [
            "tenant.view", "tenant.manage_settings", "members.view",
            "members.invite", "members.remove", "members.update_role", "audit.read",
        ],
        "admin": [
            "tenant.view", "tenant.manage_settings", "members.view",
            "members.invite", "members.remove", "members.update_role", "audit.read",
        ],
        "manager": ["tenant.view", "members.view", "members.invite", "audit.read"],
        "staff": ["tenant.view", "members.view"],
        "read_only": ["tenant.view"],
    }

    roles_table = sa.table(
        "tenant_roles",
        sa.column("id", pg.UUID(as_uuid=True)),
        sa.column("tenant_id", pg.UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("is_system", sa.Boolean),
    )
    permissions_table = sa.table(
        "tenant_permissions",
        sa.column("id", pg.UUID(as_uuid=True)),
        sa.column("role_id", pg.UUID(as_uuid=True)),
        sa.column("permission_key", sa.String),
    )

    role_rows = []
    permission_rows = []
    for role_name, permission_keys in system_roles.items():
        role_id = uuid.uuid4()
        role_rows.append({"id": role_id, "tenant_id": None, "name": role_name, "is_system": True})
        for key in permission_keys:
            permission_rows.append({"id": uuid.uuid4(), "role_id": role_id, "permission_key": key})

    op.bulk_insert(roles_table, role_rows)
    op.bulk_insert(permissions_table, permission_rows)


def downgrade() -> None:
    op.drop_table("tenant_members")
    op.drop_table("tenant_permissions")
    op.drop_table("tenant_roles")
    op.drop_table("tenant_settings")
    op.drop_table("users")
    op.drop_table("tenants")
