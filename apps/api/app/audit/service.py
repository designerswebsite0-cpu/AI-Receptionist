import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog
from app.logging import correlation_id_var


async def record_audit_event(
    db: AsyncSession,
    *,
    actor_user_id: uuid.UUID | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    before_state: dict | None = None,
    after_state: dict | None = None,
    metadata: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """Writes one audit_logs row. Never raises on its own — callers persist
    this in the same transaction as the mutation it describes so the audit
    trail and the change it records cannot drift apart.

    Single-resort deployment (product_decisions.md): no tenant_id — there is
    only ever one resort's data in this database. correlation_id is read
    automatically from the current request's context (app.logging), so
    callers don't need to thread it through manually.
    """
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            before_state=before_state,
            after_state=after_state,
            event_metadata=metadata or {},
            ip_address=ip_address,
            correlation_id=correlation_id_var.get(),
        )
    )
