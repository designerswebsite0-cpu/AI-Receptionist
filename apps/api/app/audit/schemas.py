import uuid
from datetime import datetime

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: uuid.UUID
    actor_user_id: uuid.UUID | None
    actor_name: str | None = None
    action: str
    resource_type: str
    resource_id: str | None
    before_state: dict | None
    after_state: dict | None
    event_metadata: dict
    ip_address: str | None
    correlation_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
