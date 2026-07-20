"""Customer Feedback (Phase X Stage 7). The only real write path today is
app.webchat.service.submit_feedback() calling record_webchat_feedback below
— an additive insert alongside its existing audit-log write (untouched),
so guest thumbs-up/down becomes a real, queryable dashboard item.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import NotFoundError
from app.feedback import repository
from app.feedback.models import CustomerFeedback
from app.feedback.schemas import FeedbackUpdateRequest
from app.notifications.service import notify


async def record_webchat_feedback(
    db: AsyncSession,
    *,
    rating: str,
    comment: str | None,
    conversation_id: uuid.UUID,
    customer_id: uuid.UUID,
    turn_id: uuid.UUID | None,
) -> CustomerFeedback:
    feedback = await repository.create_feedback(
        db,
        category="website_chat",
        rating=rating,
        comment=comment,
        conversation_id=conversation_id,
        customer_id=customer_id,
        turn_id=turn_id,
    )
    await db.commit()
    await db.refresh(feedback)

    await notify(
        db,
        notification_type="feedback_received",
        title="New guest feedback" if rating == "up" else "Negative guest feedback",
        body=comment,
        resource_type="conversation",
        resource_id=str(conversation_id),
    )
    return feedback


async def get_feedback_or_404(db: AsyncSession, feedback_id: uuid.UUID) -> CustomerFeedback:
    feedback = await repository.get_feedback(db, feedback_id)
    if feedback is None:
        raise NotFoundError("Feedback not found")
    return feedback


async def update_feedback(
    db: AsyncSession, *, feedback_id: uuid.UUID, body: FeedbackUpdateRequest
) -> CustomerFeedback:
    feedback = await get_feedback_or_404(db, feedback_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(feedback, field, value)
    await db.commit()
    await db.refresh(feedback)
    return feedback
