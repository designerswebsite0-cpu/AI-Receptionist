import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TimestampMixin, UUIDPrimaryKeyMixin
from app.database import Base
from app.orchestration.constants import SERVICE_REQUEST_STATUSES, SERVICE_REQUEST_TYPES


class OrchestrationTurn(Base, UUIDPrimaryKeyMixin):
    """One row per pipeline run — the operationally-useful decision trace
    (intent/entities/retrieval/tool/handoff/validation/provider), never
    chain-of-thought. See docs/phase-4/PHASE_4_IMPLEMENTATION_PLAN.md §2.
    """

    __tablename__ = "orchestration_turns"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    response_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )

    detected_intent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    intent_confidence: Mapped[float | None] = mapped_column(nullable=True)
    secondary_intents: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    extracted_entities: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    missing_entities: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    flow_state: Mapped[str | None] = mapped_column(String(50), nullable=True)

    retrieval_query: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    citations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    tool_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tool_input: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    tool_output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tool_status: Mapped[str | None] = mapped_column(String(20), nullable=True)

    handoff_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    handoff_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    handoff_priority: Mapped[str | None] = mapped_column(String(20), nullable=True)
    handoff_department: Mapped[str | None] = mapped_column(String(50), nullable=True)

    validation_result: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    provider_used: Mapped[str | None] = mapped_column(String(30), nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_usage: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class ServiceRequest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Generic 'safe enquiry, not a fake completed operation' record every
    create_*_enquiry tool writes into (booking/dining/spa/activity/
    transfer/general/complaint) — one table, not one per domain, since
    Phase 7 (Business Action Engine) is where real per-domain integrations
    land. See PHASE_4_IMPLEMENTATION_PLAN.md §2.
    """

    __tablename__ = "service_requests"
    __table_args__ = (
        CheckConstraint(f"request_type IN {SERVICE_REQUEST_TYPES}", name="ck_service_requests_type"),
        CheckConstraint(f"status IN {SERVICE_REQUEST_STATUSES}", name="ck_service_requests_status"),
        CheckConstraint("created_by IN ('ai', 'human')", name="ck_service_requests_created_by"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    request_type: Mapped[str] = mapped_column(String(30), nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    created_by: Mapped[str] = mapped_column(String(10), nullable=False)
    assigned_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
