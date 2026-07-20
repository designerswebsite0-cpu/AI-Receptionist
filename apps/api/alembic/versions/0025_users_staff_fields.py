"""Phase X Stage 4: users staff fields

Revision ID: 0025
Revises: 0024
Create Date: 2026-07-20

Adds role/status/last_login_at to `users` for the Staff Management section.
`role` is a free-text display label (default "Administrator") — deliberately
not RBAC-enforcing (product_decisions.md: single-resort, no roles system);
it exists so the dashboard can show/edit a human-readable title per staff
member, nothing more. `status` gates only whether a staff member shows as
active/inactive in the roster — it does not block login (auth stays
Supabase-session-only, unchanged); deactivating someone here is a
visibility/reporting signal for admins, not an access control.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("role", sa.String(50), nullable=False, server_default="Administrator"))
    op.add_column("users", sa.Column("status", sa.String(20), nullable=False, server_default="active"))
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint("ck_users_status", "users", "status IN ('active', 'inactive')")


def downgrade() -> None:
    op.drop_constraint("ck_users_status", "users", type_="check")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "status")
    op.drop_column("users", "role")
