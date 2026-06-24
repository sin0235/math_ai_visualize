"""Routes cho sinh đề biến thể từ MathScene."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.deps import enforce_rate_limit, require_active_user, require_trusted_origin
from app.api.routes_render import enforce_render_access
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.admin import AdminRepository
from app.schemas.scene import ProblemVariantsRequest, ProblemVariantsResponse
from app.services.ai_resolution import resolve_byok_ai_config, settings_with_byok_connection
from app.services.api_errors import bad_request_from_error
from app.services.model_registry import resolve_effective_settings
from app.services.problem_variants import generate_variants
from app.services.user_ai_settings import UserAiSettingsError

router = APIRouter(prefix="/api", tags=["diagram"])


@router.post(
    "/problem/variants",
    response_model=ProblemVariantsResponse,
    dependencies=[Depends(require_trusted_origin)],
)
async def problem_variants(
    request: ProblemVariantsRequest,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> ProblemVariantsResponse:
    await enforce_rate_limit(db, http_request, user, "problem_variants", 18 if user else 4, 60)
    await enforce_render_access(db, user)
    settings = await resolve_effective_settings(db, request.runtime_settings)
    byok_used = False
    try:
        byok = await resolve_byok_ai_config(db, user, "solver", settings)
        if byok is not None:
            settings = settings_with_byok_connection(settings, byok)
            byok_used = True
        result = await generate_variants(
            request.scene,
            settings,
            count=request.count,
            original_problem=request.original_problem,
            explicit_model=request.preferred_ai_model if not byok_used else byok.model_id,
            preferred_provider="openai_compat" if byok_used else "openrouter",
        )
    except (RuntimeError, ValueError, UserAiSettingsError) as error:
        raise bad_request_from_error(error, "problem_variants_failed") from error
    if not byok_used:
        await AdminRepository(db).record_user_usage_event(
            user.id,
            "problem_variants",
            {"count": request.count, "provider": result.provider, "model": result.model},
        )
    return ProblemVariantsResponse(
        variants=result.variants,
        provider=result.provider,
        model=result.model,
    )
