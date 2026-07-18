"""Phase 4: conversations.flow_state

Revision ID: 0020
Revises: 0019
Create Date: 2026-07-18

A finer-grained refinement WITHIN one of the canonical 11 DIALOGUE_STATES
(conversations.current_state) — not a replacement. See
docs/phase-4/PHASE_4_IMPLEMENTATION_PLAN.md §1/§3 for why current_state
stays exactly as documented in functions.md §28/architecture.md §4.4/
database.md §5. Deliberately no CHECK constraint: flow_state's allowed
values per current_state are validated in application code
(app.orchestration.flow.engine), not the schema, since the mapping itself
is orchestration logic that may evolve without a migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("flow_state", sa.String(50), nullable=True))
    op.create_index("ix_conversations_flow_state", "conversations", ["flow_state"])


def downgrade() -> None:
    op.drop_index("ix_conversations_flow_state", table_name="conversations")
    op.drop_column("conversations", "flow_state")
