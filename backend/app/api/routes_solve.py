"""
API routes for:
  POST /api/solve            — Step-by-step geometry solver (Lựa chọn 2)
"""
import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.deps import enforce_rate_limit, require_active_user, require_trusted_origin
from app.api.routes_render import enforce_render_access
from app.core.config import get_settings
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.admin import AdminRepository
from app.schemas.advisory import QualityRiskAdvisory
from app.schemas.scene import MAX_PROBLEM_TEXT_CHARS, MathScene, RenderResponse, RuntimeSettings
from app.services.ai_resolution import resolve_byok_ai_config, settings_with_byok_connection
from app.services.api_errors import bad_request_from_error
from app.services.model_registry import load_model_registry, resolve_effective_settings, resolve_task_profile
from app.services.user_ai_settings import UserAiSettingsError

router = APIRouter(prefix="/api", tags=["solver"])


class SolveRequest(BaseModel):
    scene: dict[str, Any]
    response: RenderResponse | None = None
    question: str = Field(min_length=1, max_length=MAX_PROBLEM_TEXT_CHARS)
    geometry_method: str = "oxyz"
    runtime_settings: RuntimeSettings | None = None


class SolveStepResponse(BaseModel):
    index: int
    title: str
    explanation: str
    expression: str | None = None
    result: str | None = None
    highlight: list[str] = Field(default_factory=list)
    kind: str | None = None
    formula_latex: str | None = None
    substitution_latex: str | None = None
    result_latex: str | None = None
    sub_steps: list["SolveStepResponse"] = Field(default_factory=list)
    theorem: str | None = None
    claim: str | None = None
    depends_on: list[str] = Field(default_factory=list)

SolveStepResponse.model_rebuild()


class SolveResponse(BaseModel):
    question: str
    answer: str
    steps: list[SolveStepResponse]
    warnings: list[str] = Field(default_factory=list)
    confidence: str = "verified"
    method: str = "oxyz"
    used_facts: list[dict[str, str]] = Field(default_factory=list)
    used_theorems: list[dict[str, str]] = Field(default_factory=list)
    data_issues: list[str] = Field(default_factory=list)
    advisory: QualityRiskAdvisory | None = None


@router.post("/solve", response_model=SolveResponse, dependencies=[Depends(require_trusted_origin)])
async def solve_problem(
    request: SolveRequest,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> SolveResponse:
    from app.services.solver_service import solve

    await enforce_rate_limit(db, http_request, user, "solve", 30 if user else 10, 60)
    await enforce_render_access(db, user)
    used_ai = False
    try:
        geometry_method = request.geometry_method if request.geometry_method in {"oxyz", "classical"} else "oxyz"
        _assert_solve_quality_gate(request)
        result = await asyncio.to_thread(solve, request.scene, request.question, geometry_method)
        advisory = None
        if get_settings().advisory_enabled:
            from app.services.quality_advisory import build_solve_advisory

            advisory = await asyncio.to_thread(build_solve_advisory, request.question, request.scene, result)
        settings = await resolve_effective_settings(db, request.runtime_settings)
        byok_used = False
        byok = None
        if user is not None and hasattr(db, "fetch_one"):
            try:
                byok = await resolve_byok_ai_config(db, user, "solver", settings)
            except UserAiSettingsError as error:
                raise RuntimeError(f"Cấu hình BYOK không hợp lệ: {error}") from error
        if byok is not None:
            settings = settings_with_byok_connection(settings, byok)
            solver_profile = None
            byok_used = True
        else:
            registry = await load_model_registry(db, settings)
            solver_profile = resolve_task_profile(registry, "solver_explanation")
        if geometry_method != "classical" and (settings.router9_api_key or settings.openrouter_api_key or settings.openai_compat_api_key):
            from app.services.solver_explainer import explain_solver_result

            result = await explain_solver_result(result, request.scene, settings, solver_profile, method=geometry_method)
            used_ai = True
    except Exception as e:
        from app.repositories.activity import try_log_user_activity

        await try_log_user_activity(
            db,
            user.id,
            "solve.failed",
            target_type="solve",
            metadata={"error": str(e)[:200]},
        )
        raise bad_request_from_error(e, "solve_failed") from e

    if used_ai and not byok_used:
        await AdminRepository(db).record_user_usage_event(user.id, "solver_ai", {"source": "geometry_solve"})
    from app.repositories.activity import try_log_user_activity

    await try_log_user_activity(
        db,
        user.id,
        "solve.completed",
        target_type="solve",
        metadata={"used_ai": used_ai, "geometry_method": geometry_method},
    )
    def _map_step(s) -> SolveStepResponse:
        return SolveStepResponse(
            index=s.index,
            title=s.title,
            explanation=s.explanation,
            expression=s.expression,
            result=s.result,
            highlight=s.highlight,
            kind=s.kind,
            formula_latex=s.formula_latex,
            substitution_latex=s.substitution_latex,
            result_latex=s.result_latex,
            sub_steps=[_map_step(sub) for sub in getattr(s, "sub_steps", [])],
            theorem=getattr(s, "theorem", None),
            claim=getattr(s, "claim", None),
            depends_on=getattr(s, "depends_on", []),
        )

    return SolveResponse(
        question=result.question,
        answer=result.answer,
        steps=[_map_step(s) for s in result.steps],
        warnings=result.warnings,
        confidence=getattr(result, "confidence", "verified"),
        method=getattr(result, "method", "oxyz"),
        used_facts=getattr(result, "used_facts", []),
        used_theorems=getattr(result, "used_theorems", []),
        data_issues=getattr(result, "data_issues", []),
        advisory=advisory,
    )


def _assert_solve_quality_gate(request: SolveRequest) -> None:
    from app.services.render_quality_gate import assert_render_response_safe_for_downstream, assert_scene_safe_for_downstream

    if request.response is not None:
        scene = MathScene.model_validate(request.scene)
        assert_render_response_safe_for_downstream(
            request.response,
            scene,
            operation="giải bài",
            allow_partial=False,
        )
        return
    try:
        scene = MathScene.model_validate(request.scene)
    except Exception:
        # Caller cũ có thể gửi scene solver dạng dict không phải MathScene render v2.
        # Chỉ áp quality gate đầy đủ khi có response v2 hoặc scene khớp MathScene.
        return
    assert_scene_safe_for_downstream(scene, operation="giải bài", allow_partial=False)
