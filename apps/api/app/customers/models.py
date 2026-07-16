import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.database import Base

CONTACT_TYPES = ("phone", "email", "whatsapp")


class Customer(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Cross-channel guest identity — the Customer 360 foundation.

    Single-resort deployment (product_decisions.md): no tenant_id — this
    database serves exactly one resort, so every row here already belongs
    to it implicitly.

    Structure only this phase (per roadmap.md Phase 2): `preferences` and
    `resort_preferences` are free-form JSONB buckets rather than normalized
    columns, because the AI memory layer that will populate them in a
    principled way (source/confidence/verification — rules.md §6) doesn't
    land until later phases. "Previous stays" and "communication history"
    are deliberately not columns here — they're derived by querying
    bookings (Phase 7, not yet built) and conversations (this phase) by
    customer_id rather than duplicated onto this row.
    """

    __tablename__ = "customers"

    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    preferred_channel: Mapped[str | None] = mapped_column(String(20), nullable=True)
    lifetime_value: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    loyalty_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    preferences: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    resort_preferences: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class CustomerContact(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A phone/email/WhatsApp identity resolving to one customer.

    Unique per (contact_type, value) — single-resort, so this is globally
    unique within the deployment, not scoped per tenant anymore.
    """

    __tablename__ = "customer_contacts"
    __table_args__ = (
        UniqueConstraint("contact_type", "value", name="uq_customer_contacts_type_value"),
        CheckConstraint("contact_type IN ('phone', 'email', 'whatsapp')", name="ck_customer_contacts_type"),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contact_type: Mapped[str] = mapped_column(String(20), nullable=False)
    value: Mapped[str] = mapped_column(String(320), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class CustomerNote(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A staff-authored note — a verified, attributed fact per rules.md §6,
    never an AI inference (those arrive in a later phase with their own
    source/confidence tracking, kept structurally separate)."""

    __tablename__ = "customer_notes"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str] = mapped_column(String(4000), nullable=False)


class CustomerTag(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "customer_tags"
    __table_args__ = (UniqueConstraint("customer_id", "tag", name="uq_customer_tags_customer_tag"),)

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tag: Mapped[str] = mapped_column(String(50), nullable=False)
