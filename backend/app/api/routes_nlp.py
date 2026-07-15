from fastapi import APIRouter, Depends, Request

from app.api.deps import enforce_rate_limit, get_optional_current_user, require_trusted_origin
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.schemas.auth import SystemFeatureFlags
from app.schemas.nlp import InputEnvelope, InterpretationResponse
from app.services.nlp import interpret_input
from app.services.nlp.llm import interpret_input_with_llm_fallback
from app.services.system_settings import load_feature_flags

router = APIRouter(prefix="/api/nlp", tags=["nlp"])


@router.post(
    "/interpret",
    response_model=InterpretationResponse,
    dependencies=[Depends(require_trusted_origin)],
)
async def interpret_math_input(
    envelope: InputEnvelope,
    request: Request,
    user: UserRecord | None = Depends(get_optional_current_user),
    db: DatabaseClient = Depends(get_database),
) -> InterpretationResponse:
    await enforce_rate_limit(db, request, user, "nlp_interpret", 60 if user else 30, 60)
    try:
        flags = await load_feature_flags(db)
    except Exception:
        # NLP preflight phải giữ fast path deterministic nếu settings backend tạm lỗi.
        flags = SystemFeatureFlags()
    if flags.nlp_llm_fallback_enabled and user is not None:
        await enforce_rate_limit(db, request, user, "nlp_llm_fallback", 12, 60)
        return await interpret_input_with_llm_fallback(
            envelope,
            db,
            user_id=user.id,
            enabled=True,
        )
    return interpret_input(envelope)
