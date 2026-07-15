import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog


async def record_audit_event(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID | None,
    actor_user_id: uuid.UUID | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    metadata: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """Writes one audit_logs row. Never raises on its own — callers persist
    this in the same transaction as the mutation it describes so the audit
    trail and the change it records cannot drift apart.
    """
    db.add(
        AuditLog(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            event_metadata=metadata or {},
            ip_address=ip_address,
        )
    )
