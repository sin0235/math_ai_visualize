"""
API routes for:
  POST /api/solve            — Step-by-step geometry solver (Lựa chọn 2)
"""
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.deps import enforce_rate_limit, require_active_user, require_trusted_origin
from app.api.routes_render import enforce_render_access
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.admin import AdminRepository
from app.schemas.scene import MAX_PROBLEM_TEXT_CHARS, RuntimeSettings
from app.services.api_errors import bad_request_from_error
from app.services.model_registry import load_model_registry, resolve_effective_settings, resolve_task_profile

router = APIRouter(prefix="/api", tags=["solver"])


class SolveRequest(BaseModel):
    scene: dict[str, Any]
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

SolveStepResponse.model_rebuild()


class SolveResponse(BaseModel):
    question: str
    answer: str
    steps: list[SolveStepResponse]
    warnings: list[str] = Field(default_factory=list)


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
        result = solve(request.scene, request.question)
        settings = await resolve_effective_settings(db, request.runtime_settings)
        registry = await load_model_registry(db, settings)
        solver_profile = resolve_task_profile(registry, "solver_explanation")
        if settings.router9_api_key or settings.openrouter_api_key:
            from app.services.solver_explainer import explain_solver_result

            result = await explain_solver_result(result, request.scene, settings, solver_profile, method=request.geometry_method)
            used_ai = True
    except Exception as e:
        raise bad_request_from_error(e, "solve_failed") from e

    if used_ai:
        await AdminRepository(db).record_user_usage_event(user.id, "solver_ai", {"source": "geometry_solve"})
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
        )

    return SolveResponse(
        question=result.question,
        answer=result.answer,
        steps=[_map_step(s) for s in result.steps],
        warnings=result.warnings,
    )
