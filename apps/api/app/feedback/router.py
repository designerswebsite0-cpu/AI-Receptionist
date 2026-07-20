import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import PageParams, build_page_meta
from app.common.responses import success
from app.customers import repository as customers_repository
from app.database import get_db
from app.deps import get_current_user
from app.feedback import repository, service
from app.feedback.schemas import FeedbackOut, FeedbackStatsOut, FeedbackUpdateRequest
from app.users.models import User

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])


@router.get("")
async def list_feedback(
    category: str | None = Query(default=None),
    rating: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    params = PageParams(page=page, page_size=page_size)
    items_raw, total = await repository.list_feedback(
        db, category=category, rating=rating, status=status, offset=params.offset, limit=params.page_size
    )
    names = await customers_repository.get_names_by_ids(db, [f.customer_id for f in items_raw if f.customer_id])
    items = [
        FeedbackOut.model_validate(f)
        .model_copy(update={"customer_name": names.get(f.customer_id) if f.customer_id else None})
        .model_dump(mode="json")
        for f in items_raw
    ]
    return success({"items": items, "meta": build_page_meta(params, total).model_dump()})


@router.get("/stats")
async def get_feedback_stats(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    up_count, down_count, total, by_category = await repository.get_stats(db)
    positive_rate = (up_count / total) if total else None
    stats = FeedbackStatsOut(
        total=total, up_count=up_count, down_count=down_count, positive_rate=positive_rate, by_category=by_category
    )
    return success(stats.model_dump(mode="json"))


@router.get("/{feedback_id}")
async def get_feedback(
    feedback_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    feedback = await service.get_feedback_or_404(db, feedback_id)
    names = await customers_repository.get_names_by_ids(db, [feedback.customer_id] if feedback.customer_id else [])
    out = FeedbackOut.model_validate(feedback).model_copy(
        update={"customer_name": names.get(feedback.customer_id) if feedback.customer_id else None}
    )
    return success(out.model_dump(mode="json"))


@router.patch("/{feedback_id}")
async def update_feedback(
    feedback_id: uuid.UUID,
    body: FeedbackUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    feedback = await service.update_feedback(db, feedback_id=feedback_id, body=body)
    return success(FeedbackOut.model_validate(feedback).model_dump(mode="json"))
