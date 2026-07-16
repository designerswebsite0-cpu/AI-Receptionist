import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_audit_event
from app.errors import ConflictError, NotFoundError
from app.resort import repository
from app.resort.models import ResortSettings
from app.resort.schemas import ResortSettingsCreateRequest, ResortSettingsUpdateRequest


async def create_resort_settings(
    db: AsyncSession, *, body: ResortSettingsCreateRequest, actor_user_id: uuid.UUID | None
) -> ResortSettings:
    if await repository.get_resort_settings(db) is not None:
        raise ConflictError("Resort settings already exist for this deployment — use update instead")

    settings_row = ResortSettings(**body.model_dump())
    db.add(settings_row)
    await db.flush()

    await record_audit_event(
        db,
        actor_user_id=actor_user_id,
        action="resort_settings.created",
        resource_type="resort_settings",
        resource_id=str(settings_row.id),
        metadata={"resort_name": body.resort_name},
    )
    await db.commit()
    await db.refresh(settings_row)
    return settings_row


async def get_resort_settings_or_404(db: AsyncSession) -> ResortSettings:
    settings_row = await repository.get_resort_settings(db)
    if settings_row is None:
        raise NotFoundError("Resort settings have not been configured yet")
    return settings_row


async def update_resort_settings(
    db: AsyncSession, *, body: ResortSettingsUpdateRequest, actor_user_id: uuid.UUID | None
) -> ResortSettings:
    settings_row = await get_resort_settings_or_404(db)

    updates = body.model_dump(exclude_unset=True)
    before_state = {field: getattr(settings_row, field) for field in updates}
    for field, value in updates.items():
        setattr(settings_row, field, value)

    await record_audit_event(
        db,
        actor_user_id=actor_user_id,
        action="resort_settings.updated",
        resource_type="resort_settings",
        resource_id=str(settings_row.id),
        before_state=before_state,
        after_state=updates,
        metadata={"fields": list(updates.keys())},
    )
    await db.commit()
    await db.refresh(settings_row)
    return settings_row
