"""
API routes for:
  POST /api/solve            — Step-by-step geometry solver (Lựa chọn 2)
"""
import asyncio

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.deps import enforce_rate_limit, require_active_user, require_trusted_origin
from app.api.routes_render import enforce_render_access
from app.core.config import get_settings
from app.core.logging import get_request_id
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.admin import AdminRepository
from app.schemas.advisory import QualityRiskAdvisory
from app.schemas.math_solution import Solution
from app.schemas.geometry_reasoning import GeometryProofPlan
from app.schemas.scene import MAX_PROBLEM_TEXT_CHARS, RuntimeSettings
from app.schemas.scene_v3 import CommittedSceneRefV3
from app.schemas.nlp import ExplanationPlan, InputEnvelope
from app.services.ai_resolution import resolve_byok_ai_config, settings_with_byok_connection
from app.services.api_errors import api_error, bad_request_from_error
from app.services.committed_scene_v3 import CommittedSceneError, load_committed_scene_v3
from app.services.downstream_scene_v3 import scene_v3_to_solver_input
from app.services.math_solution_projectors import project_geometry_solution
from app.services.model_registry import load_model_registry, resolve_effective_settings, resolve_task_profile
from app.services.nlp_rollout import evaluate_configured_nlp_rollout, log_nlp_taxonomy
from app.services.user_ai_settings import UserAiSettingsError

router = APIRouter(prefix="/api", tags=["solver"])


class SolveRequest(BaseModel):
    scene_ref: CommittedSceneRefV3
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
    theorem_id: str | None = None
    claim: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    highlight_object_ids: list[str] = Field(default_factory=list)
    relation_ids: list[str] = Field(default_factory=list)
    construction_actions: list[dict[str, object]] = Field(default_factory=list)

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
    proof_plan: GeometryProofPlan | None = None
    data_issues: list[str] = Field(default_factory=list)
    advisory: QualityRiskAdvisory | None = None
    grounding: ExplanationPlan | None = None
    realization_status: str = "deterministic"
    realization_fallback_reason: str | None = None
    solution_ir: Solution | None = None


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
        committed = await load_committed_scene_v3(db, user.id, request.scene_ref)
        scene_input = scene_v3_to_solver_input(committed.result.scene, committed.result.verification)
        geometry_method = request.geometry_method if request.geometry_method in {"oxyz", "classical"} else "oxyz"
        rollout = await evaluate_configured_nlp_rollout(
            db,
            InputEnvelope(
                text=request.question,
                target="geometry_solve",
                context={
                    "scene_topic": committed.result.scene.topic,
                    "scene_id": committed.result.scene.scene_id,
                    "geometry_method": request.geometry_method,
                    "scene_objects": [
                        obj.model_dump(
                            mode="json",
                            include={"id", "label", "type", "point_ids", "from_point_id", "to_point_id"},
                            exclude_none=True,
                        )
                        for obj in committed.result.scene.objects
                    ],
                },
            ),
            user_id=user.id,
            request_id=get_request_id(),
            legacy_status="accepted",
            legacy_canonical=request.question,
        )
        question = request.question
        if rollout and rollout.can_apply and rollout.candidate:
            question = rollout.candidate.canonical_text or rollout.response.normalized_text
        result = await asyncio.to_thread(solve, scene_input, question, geometry_method)
        from app.services.nlp.grounding import build_geometry_explanation_plan

        if result.grounding is None:
            result.grounding = build_geometry_explanation_plan(result).model_dump(mode="json")
        advisory = None
        if get_settings().advisory_enabled:
            from app.services.quality_advisory import build_solve_advisory

            advisory = await asyncio.to_thread(build_solve_advisory, question, scene_input, result)
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
        ai_configured = settings.router9_api_key or settings.openrouter_api_key or settings.openai_compat_api_key
        proof_verified = getattr(result, "confidence", "verified") == "verified" and bool(result.steps)
        if ai_configured and (geometry_method != "classical" or proof_verified):
            from app.services.solver_explainer import explain_solver_result

            result = await explain_solver_result(result, scene_input, settings, solver_profile, method=geometry_method)
            used_ai = result.realization_status == "ai_validated"
    except CommittedSceneError as error:
        raise api_error(error.status_code, str(error), error.code) from error
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
    if getattr(result, "confidence", "verified") == "insufficient":
        await log_nlp_taxonomy(
            db,
            user_id=user.id,
            taxonomy_code="solver_unsupported",
            target="geometry_solve",
            status="unsupported",
            request_id=get_request_id(),
        )
    if getattr(result, "realization_status", "deterministic") == "fallback":
        await log_nlp_taxonomy(
            db,
            user_id=user.id,
            taxonomy_code="explainer_fallback",
            target="geometry_solve",
            status="accepted",
            request_id=get_request_id(),
        )
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
            theorem_id=getattr(s, "theorem_id", None),
            claim=getattr(s, "claim", None),
            depends_on=getattr(s, "depends_on", []),
            highlight_object_ids=getattr(s, "highlight_object_ids", []),
            relation_ids=getattr(s, "relation_ids", []),
            construction_actions=getattr(s, "construction_actions", []),
        )

    response = SolveResponse(
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
        grounding=getattr(result, "grounding", None),
        realization_status=getattr(result, "realization_status", "deterministic"),
        realization_fallback_reason=getattr(result, "realization_fallback_reason", None),
    )
    response.solution_ir = project_geometry_solution(
        request,
        response,
        scene_topic=committed.result.scene.topic,
    )
    return response
