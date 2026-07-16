"""resort_settings — single-resort configuration

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-16

Part of Phase 2.5 (single-resort architecture refactor, see
docs/product_decisions.md). Introduces the replacement for tenant_settings;
migration 0008 removes the tenant system itself.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resort_settings",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("singleton", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("resort_name", sa.String(200), nullable=False),
        sa.Column("legal_name", sa.String(200), nullable=True),
        sa.Column("description", sa.String(4000), nullable=True),
        sa.Column("address", sa.String(300), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("state", sa.String(100), nullable=True),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("postal_code", sa.String(20), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("whatsapp", sa.String(30), nullable=True),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("currency", sa.String(10), nullable=False, server_default="USD"),
        sa.Column("default_language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("check_in_time", sa.String(10), nullable=True),
        sa.Column("check_out_time", sa.String(10), nullable=True),
        sa.Column("logo_url", sa.String(1000), nullable=True),
        sa.Column("primary_brand_color", sa.String(20), nullable=True),
        sa.Column("secondary_brand_color", sa.String(20), nullable=True),
        sa.Column("website_url", sa.String(500), nullable=True),
        sa.Column("settings_metadata", pg.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
            onupdate=sa.func.now(), nullable=False,
        ),
        sa.UniqueConstraint("singleton", name="uq_resort_settings_singleton"),
        sa.CheckConstraint("singleton = true", name="ck_resort_settings_singleton"),
    )


def downgrade() -> None:
    op.drop_table("resort_settings")
