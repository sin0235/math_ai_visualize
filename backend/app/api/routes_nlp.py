from fastapi import APIRouter, Depends, Request

from app.api.deps import enforce_rate_limit, get_optional_current_user, require_trusted_origin
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.schemas.nlp import InputEnvelope, InterpretationResponse
from app.services.nlp import interpret_input

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
    return interpret_input(envelope)