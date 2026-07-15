"""customers, conversations, messages — Phase 2 shared conversation foundation

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CHANNELS = ("whatsapp", "webchat")
CONTACT_TYPES = ("phone", "email", "whatsapp")
STATUSES = (
    "open", "waiting_for_guest", "waiting_for_staff", "ai_handling",
    "human_handling", "escalated", "closed", "blocked",
)
PRIORITIES = ("low", "normal", "high", "urgent")
DIALOGUE_STATES = (
    "greeting", "discovering_needs", "collecting_information", "recommending",
    "booking", "waiting", "confirmation", "upselling", "support", "escalation", "closed",
)
STATE_CHANGED_BY = ("ai", "human", "system")
DIRECTIONS = ("inbound", "outbound")
SENDER_TYPES = ("customer", "ai", "human", "system")
CONTENT_TYPES = ("text", "image", "document", "audio", "video")
DELIVERY_STATUSES = ("pending", "sent", "delivered", "failed")
ATTACHMENT_TYPES = ("image", "document", "audio", "video")


def _fk(name: str, target: str, ondelete: str, *, nullable: bool = False) -> sa.Column:
    return sa.Column(name, pg.UUID(as_uuid=True), sa.ForeignKey(target, ondelete=ondelete), nullable=nullable)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
            onupdate=sa.func.now(), nullable=False,
        ),
    ]


def upgrade() -> None:
    # --- customers -----------------------------------------------------
    op.create_table(
        "customers",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        _fk("tenant_id", "tenants.id", "CASCADE"),
        sa.Column("full_name", sa.String(200), nullable=True),
        sa.Column("preferred_language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("preferred_channel", sa.String(20), nullable=True),
        sa.Column("lifetime_value", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("loyalty_reference", sa.String(100), nullable=True),
        sa.Column("preferences", pg.JSONB, nullable=False, server_default="{}"),
        sa.Column("resort_preferences", pg.JSONB, nullable=False, server_default="{}"),
        *_timestamps(),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_customers_tenant_id", "customers", ["tenant_id"])

    op.create_table(
        "customer_contacts",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        _fk("tenant_id", "tenants.id", "CASCADE"),
        _fk("customer_id", "customers.id", "CASCADE"),
        sa.Column("contact_type", sa.String(20), nullable=False),
        sa.Column("value", sa.String(320), nullable=False),
        sa.Column("is_primary", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("verified", sa.Boolean, nullable=False, server_default=sa.false()),
        *_timestamps(),
        sa.UniqueConstraint("tenant_id", "contact_type", "value", name="uq_customer_contacts_tenant_type_value"),
        sa.CheckConstraint(f"contact_type IN {CONTACT_TYPES}", name="ck_customer_contacts_type"),
    )
    op.create_index("ix_customer_contacts_tenant_id", "customer_contacts", ["tenant_id"])
    op.create_index("ix_customer_contacts_customer_id", "customer_contacts", ["customer_id"])

    op.create_table(
        "customer_notes",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        _fk("tenant_id", "tenants.id", "CASCADE"),
        _fk("customer_id", "customers.id", "CASCADE"),
        _fk("author_user_id", "users.id", "SET NULL", nullable=True),
        sa.Column("note", sa.String(4000), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_customer_notes_tenant_id", "customer_notes", ["tenant_id"])
    op.create_index("ix_customer_notes_customer_id", "customer_notes", ["customer_id"])

    op.create_table(
        "customer_tags",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        _fk("tenant_id", "tenants.id", "CASCADE"),
        _fk("customer_id", "customers.id", "CASCADE"),
        sa.Column("tag", sa.String(50), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("customer_id", "tag", name="uq_customer_tags_customer_tag"),
    )
    op.create_index("ix_customer_tags_tenant_id", "customer_tags", ["tenant_id"])
    op.create_index("ix_customer_tags_customer_id", "customer_tags", ["customer_id"])

    # --- conversations ---------------------------------------------------
    op.create_table(
        "conversations",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        _fk("tenant_id", "tenants.id", "CASCADE"),
        _fk("customer_id", "customers.id", "RESTRICT"),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="open"),
        sa.Column("current_state", sa.String(30), nullable=False, server_default="greeting"),
        _fk("assigned_agent_id", "users.id", "SET NULL", nullable=True),
        sa.Column("priority", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ai_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("human_active", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("summary", sa.String(4000), nullable=True),
        sa.Column("tags", pg.JSONB, nullable=False, server_default="[]"),
        sa.Column("conversation_metadata", pg.JSONB, nullable=False, server_default="{}"),
        *_timestamps(),
        sa.CheckConstraint(f"channel IN {CHANNELS}", name="ck_conversations_channel"),
        sa.CheckConstraint(f"status IN {STATUSES}", name="ck_conversations_status"),
        sa.CheckConstraint(f"priority IN {PRIORITIES}", name="ck_conversations_priority"),
        sa.CheckConstraint(f"current_state IN {DIALOGUE_STATES}", name="ck_conversations_current_state"),
    )
    op.create_index("ix_conversations_tenant_id", "conversations", ["tenant_id"])
    op.create_index("ix_conversations_customer_id", "conversations", ["customer_id"])
    op.create_index("ix_conversations_status", "conversations", ["status"])
    op.create_index("ix_conversations_assigned_agent_id", "conversations", ["assigned_agent_id"])

    op.create_table(
        "conversation_state_events",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        _fk("tenant_id", "tenants.id", "CASCADE"),
        _fk("conversation_id", "conversations.id", "CASCADE"),
        sa.Column("from_state", sa.String(30), nullable=True),
        sa.Column("to_state", sa.String(30), nullable=False),
        sa.Column("changed_by", sa.String(20), nullable=False),
        sa.Column("event_metadata", pg.JSONB, nullable=False, server_default="{}"),
        *_timestamps(),
        sa.CheckConstraint(f"changed_by IN {STATE_CHANGED_BY}", name="ck_conv_state_events_changed_by"),
    )
    op.create_index("ix_conv_state_events_tenant_id", "conversation_state_events", ["tenant_id"])
    op.create_index("ix_conv_state_events_conversation_id", "conversation_state_events", ["conversation_id"])

    # --- messages ---------------------------------------------------------
    op.create_table(
        "messages",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        _fk("tenant_id", "tenants.id", "CASCADE"),
        _fk("conversation_id", "conversations.id", "CASCADE"),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("sender_type", sa.String(20), nullable=False),
        _fk("sender_user_id", "users.id", "SET NULL", nullable=True),
        sa.Column("content_type", sa.String(20), nullable=False, server_default="text"),
        sa.Column("content_text", sa.String(8000), nullable=True),
        sa.Column("delivery_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_message_id", sa.String(200), nullable=True),
        sa.Column("message_metadata", pg.JSONB, nullable=False, server_default="{}"),
        *_timestamps(),
        sa.CheckConstraint(f"direction IN {DIRECTIONS}", name="ck_messages_direction"),
        sa.CheckConstraint(f"sender_type IN {SENDER_TYPES}", name="ck_messages_sender_type"),
        sa.CheckConstraint(f"content_type IN {CONTENT_TYPES}", name="ck_messages_content_type"),
        sa.CheckConstraint(f"delivery_status IN {DELIVERY_STATUSES}", name="ck_messages_delivery_status"),
    )
    op.create_index("ix_messages_tenant_id", "messages", ["tenant_id"])
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_external_message_id", "messages", ["external_message_id"])

    op.create_table(
        "message_attachments",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        _fk("tenant_id", "tenants.id", "CASCADE"),
        _fk("message_id", "messages.id", "CASCADE"),
        sa.Column("attachment_type", sa.String(20), nullable=False),
        sa.Column("storage_path", sa.String(1000), nullable=False),
        sa.Column("file_name", sa.String(300), nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("size_bytes", sa.BigInteger, nullable=True),
        *_timestamps(),
        sa.CheckConstraint(f"attachment_type IN {ATTACHMENT_TYPES}", name="ck_attachments_type"),
    )
    op.create_index("ix_message_attachments_tenant_id", "message_attachments", ["tenant_id"])
    op.create_index("ix_message_attachments_message_id", "message_attachments", ["message_id"])


def downgrade() -> None:
    op.drop_table("message_attachments")
    op.drop_table("messages")
    op.drop_table("conversation_state_events")
    op.drop_table("conversations")
    op.drop_table("customer_tags")
    op.drop_table("customer_notes")
    op.drop_table("customer_contacts")
    op.drop_table("customers")
