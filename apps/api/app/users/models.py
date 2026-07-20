import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TimestampMixin
from app.database import Base
from app.users.constants import USER_STATUSES


class User(Base, TimestampMixin):
    """Profile mirror of Supabase auth.users, keyed by the same UUID.

    Supabase Auth remains the source of truth for credentials; this table
    only stores platform-visible profile fields and is upserted on first
    sign-in / token verification.
    """

    __tablename__ = "users"
    __table_args__ = (CheckConstraint(f"status IN {USER_STATUSES}", name="ck_users_status"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    # Display-only label, not an RBAC role — this deployment has no
    # permissions system (product_decisions.md, single-resort refactor).
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="Administrator")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
