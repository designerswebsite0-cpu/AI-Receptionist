"""seed customers.*/conversations.* permissions onto existing roles

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-16

Adds only the NEW permission rows introduced by Phase 2 (see
app/roles/seed_data.py::PHASE_2_PERMISSIONS) to the 5 system roles that
migration 0001 already seeded. Does not touch or re-insert anything 0001
created — migrations must stay additive and reproducible.
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Mirrors app/roles/seed_data.py::SYSTEM_ROLES' Phase 2 additions at
# migration-authoring time — frozen here for the same reproducibility
# reason migration 0001 freezes its own seed data.
NEW_PERMISSIONS_BY_ROLE = {
    "owner": ["customers.view", "customers.manage", "conversations.view", "conversations.manage"],
    "admin": ["customers.view", "customers.manage", "conversations.view", "conversations.manage"],
    "manager": ["customers.view", "customers.manage", "conversations.view", "conversations.manage"],
    "staff": ["customers.view", "customers.manage", "conversations.view", "conversations.manage"],
    "read_only": ["customers.view", "conversations.view"],
}


def upgrade() -> None:
    bind = op.get_bind()
    role_rows = bind.execute(
        sa.text("SELECT id, name FROM tenant_roles WHERE tenant_id IS NULL")
    ).fetchall()
    role_id_by_name = {name: role_id for role_id, name in role_rows}

    permissions_table = sa.table(
        "tenant_permissions",
        sa.column("id", sa.dialects.postgresql.UUID(as_uuid=True)),
        sa.column("role_id", sa.dialects.postgresql.UUID(as_uuid=True)),
        sa.column("permission_key", sa.String),
    )

    new_rows = []
    for role_name, permission_keys in NEW_PERMISSIONS_BY_ROLE.items():
        role_id = role_id_by_name.get(role_name)
        if role_id is None:
            continue
        for key in permission_keys:
            new_rows.append({"id": uuid.uuid4(), "role_id": role_id, "permission_key": key})

    if new_rows:
        op.bulk_insert(permissions_table, new_rows)


def downgrade() -> None:
    bind = op.get_bind()
    keys = sorted({key for keys in NEW_PERMISSIONS_BY_ROLE.values() for key in keys})
    bind.execute(
        sa.text("DELETE FROM tenant_permissions WHERE permission_key = ANY(:keys)"),
        {"keys": keys},
    )
