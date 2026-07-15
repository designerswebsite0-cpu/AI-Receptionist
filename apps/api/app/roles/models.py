import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TimestampMixin
from app.database import Base


class TenantRole(Base, TimestampMixin):
    """A role a tenant member can hold.

    tenant_id is nullable: the 5 system roles (owner/admin/manager/staff/
    read_only) are seeded once with tenant_id = NULL and shared by every
    tenant. Per-tenant custom roles are a future extension that reuses this
    same table without a redesign.
    """

    __tablename__ = "tenant_roles"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_tenant_roles_tenant_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class TenantPermission(Base, TimestampMixin):
    """A single permission key granted to a role."""

    __tablename__ = "tenant_permissions"
    __table_args__ = (UniqueConstraint("role_id", "permission_key", name="uq_role_permission"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant_roles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    permission_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
