import uuid

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TimestampMixin
from app.database import Base


class User(Base, TimestampMixin):
    """Profile mirror of Supabase auth.users, keyed by the same UUID.

    Supabase Auth remains the source of truth for credentials; this table
    only stores platform-visible profile fields and is upserted on first
    sign-in / token verification.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
