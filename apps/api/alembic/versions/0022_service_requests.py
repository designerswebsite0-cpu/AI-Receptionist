"""Phase 4: service_requests

Revision ID: 0022
Revises: 0021
Create Date: 2026-07-18

Generic "safe enquiry, not a fake completed operation" record — see
docs/phase-4/PHASE_4_IMPLEMENTATION_PLAN.md §2 for why this is one table
rather than one per tool domain (booking/dining/spa/activity/transfer).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op
from app.orchestration.constants import SERVICE_REQUEST_STATUSES, SERVICE_REQUEST_TYPES

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "service_requests",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_id", pg.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "customer_id", pg.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("request_type", sa.String(30), nullable=False),
        sa.Column("details", pg.JSONB, nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("created_by", sa.String(10), nullable=False),
        sa.Column(
            "assigned_agent_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
            onupdate=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(f"request_type IN {SERVICE_REQUEST_TYPES}", name="ck_service_requests_type"),
        sa.CheckConstraint(f"status IN {SERVICE_REQUEST_STATUSES}", name="ck_service_requests_status"),
        sa.CheckConstraint("created_by IN ('ai', 'human')", name="ck_service_requests_created_by"),
    )
    op.create_index("ix_service_requests_conversation_id", "service_requests", ["conversation_id"])
    op.create_index("ix_service_requests_customer_id", "service_requests", ["customer_id"])
    op.create_index("ix_service_requests_status", "service_requests", ["status"])


def downgrade() -> None:
    op.drop_index("ix_service_requests_status", table_name="service_requests")
    op.drop_index("ix_service_requests_customer_id", table_name="service_requests")
    op.drop_index("ix_service_requests_conversation_id", table_name="service_requests")
    op.drop_table("service_requests")
