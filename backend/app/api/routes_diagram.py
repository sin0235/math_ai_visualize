"""Routes cho sinh đề biến thể từ MathScene."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.deps import enforce_rate_limit, require_active_user, require_trusted_origin
from app.api.routes_render import enforce_render_access
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.admin import AdminRepository
from app.schemas.scene import MAX_MODEL_ID_CHARS, MAX_PROBLEM_TEXT_CHARS, ProblemVariantsResponse, RuntimeSettings
from app.schemas.scene_v3 import CommittedSceneRefV3
from app.services.ai_resolution import resolve_byok_ai_config, settings_with_byok_connection
from app.services.api_errors import api_error, bad_request_from_error
from app.services.committed_scene_v3 import CommittedSceneError, load_committed_scene_v3
from app.services.downstream_scene_v3 import scene_v3_to_variants_input
from app.services.model_registry import resolve_effective_settings
from app.services.problem_variants import generate_variants
from app.services.user_ai_settings import UserAiSettingsError

router = APIRouter(prefix="/api", tags=["diagram"])


class ProblemVariantsRequestV3(BaseModel):
    scene_ref: CommittedSceneRefV3
    count: int = Field(default=3, ge=1, le=10)
    original_problem: str | None = Field(default=None, max_length=MAX_PROBLEM_TEXT_CHARS)
    preferred_ai_model: str | None = Field(default=None, max_length=MAX_MODEL_ID_CHARS)
    runtime_settings: RuntimeSettings | None = None


@router.post(
    "/problem/variants",
    response_model=ProblemVariantsResponse,
    dependencies=[Depends(require_trusted_origin)],
)
async def problem_variants(
    request: ProblemVariantsRequestV3,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> ProblemVariantsResponse:
    await enforce_rate_limit(db, http_request, user, "problem_variants", 18 if user else 4, 60)
    await enforce_render_access(db, user)
    byok_used = False
    try:
        from app.core.config import get_settings as _get_settings
        from app.services.prompt_security import enforce_prompt_injection_gate

        if request.original_problem:
            enforce_prompt_injection_gate(
                request.original_problem,
                mode=_get_settings().prompt_injection_gate_mode,
            )
        committed = await load_committed_scene_v3(db, user.id, request.scene_ref)
        scene_input = scene_v3_to_variants_input(committed.result.scene)
        settings = await resolve_effective_settings(db, request.runtime_settings)
        byok = await resolve_byok_ai_config(db, user, "solver", settings)
        if byok is not None:
            settings = settings_with_byok_connection(settings, byok)
            byok_used = True
        result = await generate_variants(
            scene_input,
            settings,
            count=request.count,
            original_problem=request.original_problem,
            explicit_model=request.preferred_ai_model if not byok_used else byok.model_id,
            preferred_provider="openai_compat" if byok_used else "openrouter",
        )
    except CommittedSceneError as error:
        raise api_error(error.status_code, str(error), error.code) from error
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
