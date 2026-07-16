from sqlalchemy import Boolean, CheckConstraint, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TimestampMixin, UUIDPrimaryKeyMixin
from app.database import Base


class ResortSettings(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Single-resort configuration. Exactly one row may ever exist per
    deployment — enforced by `singleton` being a fixed value under a
    UNIQUE constraint, not just an application-layer check, since this
    replaces the old tenant_settings row that used to be scoped per tenant.
    """

    __tablename__ = "resort_settings"
    __table_args__ = (
        UniqueConstraint("singleton", name="uq_resort_settings_singleton"),
        CheckConstraint("singleton = true", name="ck_resort_settings_singleton"),
    )

    singleton: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    resort_name: Mapped[str] = mapped_column(String(200), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    whatsapp: Mapped[str | None] = mapped_column(String(30), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    default_language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    check_in_time: Mapped[str | None] = mapped_column(String(10), nullable=True)
    check_out_time: Mapped[str | None] = mapped_column(String(10), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    primary_brand_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    secondary_brand_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    settings_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
