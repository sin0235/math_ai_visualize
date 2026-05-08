from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import enforce_rate_limit, require_active_user, require_trusted_origin
from app.db.models import FeedbackRecord, UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.admin import AdminRepository
from app.repositories.feedback import FeedbackRepository, PendingFeedbackError
from app.schemas.feedback import FeedbackCreateRequest, FeedbackResponse, FeedbackStatusResponse

router = APIRouter(prefix="/api/feedback", tags=["feedback"])
PENDING_FEEDBACK_MESSAGE = "Bạn đã có góp ý đang chờ tiếp nhận. Hãy chờ admin xử lý trước khi gửi góp ý mới."


@router.get("/status", response_model=FeedbackStatusResponse)
async def feedback_status(user: UserRecord = Depends(require_active_user), db: DatabaseClient = Depends(get_database)) -> FeedbackStatusResponse:
    repo = FeedbackRepository(db)
    pending = await repo.find_pending_for_user(user.id)
    latest = await repo.latest_for_user(user.id)
    return FeedbackStatusResponse(
        can_submit=pending is None,
        pending_feedback=feedback_response(pending) if pending else None,
        latest_feedback=feedback_response(latest) if latest else None,
    )


@router.get("", response_model=list[FeedbackResponse])
async def list_my_feedback(user: UserRecord = Depends(require_active_user), db: DatabaseClient = Depends(get_database)) -> list[FeedbackResponse]:
    items = await FeedbackRepository(db).list_for_user(user.id)
    return [feedback_response(item) for item in items]


@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_trusted_origin)])
async def create_feedback(
    request: FeedbackCreateRequest,
    raw_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> FeedbackResponse:
    await enforce_rate_limit(db, raw_request, user, "feedback_submit", 3, 3600)
    try:
        feedback = await FeedbackRepository(db).create(user.id, request.subject, request.message)
    except PendingFeedbackError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=PENDING_FEEDBACK_MESSAGE) from error
    await AdminRepository(db).audit(user.id, "feedback.submitted", "feedback", feedback.id, {"subject": feedback.subject})
    return feedback_response(feedback)


def feedback_response(feedback: FeedbackRecord) -> FeedbackResponse:
    return FeedbackResponse(
        id=feedback.id,
        subject=feedback.subject,
        message=feedback.message,
        status=feedback.status,  # type: ignore[arg-type]
        admin_note=feedback.admin_note,
        created_at=feedback.created_at,
        updated_at=feedback.updated_at,
        resolved_at=feedback.resolved_at,
    )
