from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.math_curriculum import (
    CURRICULUM_VERSION,
    SKILLS,
    skills_for_algebra_problem,
    skills_for_function_problem,
    skills_for_geometry_problem,
)
from app.schemas.algebra import AlgebraSolveRequest, AlgebraSolveResponse
from app.schemas.analysis import AnalyzeRequest, AnalyzeResponse, AnalyzerBaseRequest
from app.schemas.math_problem import (
    CurriculumReference,
    ExpressionProblemInput,
    FunctionAnalysisProblemInput,
    GeometrySceneProblemInput,
    ProblemEnvelope,
    ProblemSource,
)
from app.schemas.math_solution import (
    Exactness,
    Solution,
    SolutionClaim,
    SolutionStatus,
    SolutionStep,
    SolutionValue,
    VerificationEvidence,
)
from app.services.math_capabilities import geometry_verifier_methods, resolve_problem_capabilities


CAPABILITY_VERSION = "legacy-solver-adapters-v1"


def project_algebra_solution(request: AlgebraSolveRequest, response: AlgebraSolveResponse) -> Solution:
    skill_ids = skills_for_algebra_problem(response.topic, response.problem_type, response.normalized_input)
    status = _algebra_status(response)
    exactness = _algebra_exactness(response)
    evidence = [
        VerificationEvidence(
            policy_methods=_verification_policy_methods(skill_ids),
            status=_check_status(check.status),
            method=check.name,
            detail=check.detail,
        )
        for check in response.verification.checks
    ]
    if response.verification.status == "verified" and not evidence:
        evidence.append(
            VerificationEvidence(
                policy_methods=_verification_policy_methods(skill_ids),
                status="pass",
                method="legacy_algebra_verifier",
                detail="Legacy verifier báo verified.",
            )
        )

    problem = ProblemEnvelope(
        domain="algebra",
        task=response.problem_type,
        source=ProblemSource(
            kind=_algebra_source_kind(response),
            original=response.input,
            canonical=response.normalized_input,
            provenance={"interpretation_source": response.input_interpretation.source} if response.input_interpretation else {},
        ),
        curriculum=_curriculum_reference(skill_ids),
        input=ExpressionProblemInput(
            expression=response.normalized_input,
            variables=request.variables or (response.input_interpretation.variables if response.input_interpretation else []),
            parameters=request.parameters,
            domain=request.domain,
        ),
        goal=response.problem_type,
        assumptions=list(dict.fromkeys(response.assumptions)),
        constraints=_algebra_constraints(request),
    )
    return Solution(
        capability_version=CAPABILITY_VERSION,
        capability=resolve_problem_capabilities(problem),
        problem=problem,
        status=status,
        exactness=exactness,
        result=SolutionValue(
            text=response.answer,
            latex=response.answer_latex,
            exact=response.solution_set.text or None,
            data=response.solution_set.model_dump(mode="json"),
        ) if response.answer else None,
        steps=[_algebra_step(step, f"algebra-step-{index}", index) for index, step in enumerate(response.steps, 1)],
        assumptions=response.assumptions,
        warnings=[*response.warnings, *response.errors],
        unsupported_reason=response.answer if status == "unsupported" else None,
        verification=evidence,
        artifacts={"milestones": response.milestones},
    )


def project_function_solution(
    request: AnalyzeRequest | AnalyzerBaseRequest,
    response: AnalyzeResponse,
) -> Solution:
    skill_ids = skills_for_function_problem(response.evaluated_expression or response.expression, "analyze")
    verification = response.verification
    status = _function_status(response)
    exactness = _verification_exactness(verification.status if verification else None)
    evidence = [
        VerificationEvidence(
            policy_methods=_verification_policy_methods(skill_ids),
            status=_check_status(check.status),
            method=check.method,
            detail=check.detail or check.name,
            error_bound=check.error_bound,
        )
        for check in (verification.checks if verification else [])
    ]
    if verification and verification.status == "verified" and not evidence:
        evidence.append(
            VerificationEvidence(
                policy_methods=_verification_policy_methods(skill_ids),
                status="pass",
                method="function_analysis_verifier",
                detail="Function analyzer báo verified.",
            )
        )

    source_kind = "ocr" if request.provenance else "manual"
    provenance = request.provenance.model_dump(mode="json") if request.provenance else {}
    parameters = request.parameters.model_dump(mode="json", exclude_none=True) if request.parameters else {}
    problem = ProblemEnvelope(
        domain="function",
        task="analyze",
        source=ProblemSource(
            kind=source_kind,
            original=request.expression,
            canonical=response.evaluated_expression or response.expression,
            provenance=provenance,
        ),
        curriculum=_curriculum_reference(skill_ids),
        input=FunctionAnalysisProblemInput(
            expression=response.evaluated_expression or response.expression,
            parameters=parameters,
            requested_analyses=_requested_function_analyses(request),
        ),
        goal="Khảo sát hàm số",
        constraints=_function_constraints(request),
    )
    return Solution(
        capability_version=CAPABILITY_VERSION,
        capability=resolve_problem_capabilities(problem),
        problem=problem,
        status=status,
        exactness=exactness,
        result=SolutionValue(
            text=response.evaluated_expression or response.expression,
            latex=response.evaluated_expression_latex or response.expression_latex,
            data={
                "domain": response.domain,
                "range": response.range_val,
                "derivative": response.derivative,
                "parity": response.parity,
            },
        ) if not response.error else None,
        steps=[
            SolutionStep(
                step_id=f"function-step-{step.order}",
                order=step.order,
                title=step.title,
                explanation="; ".join(step.evidence) or step.title,
                after=step.formula_latex,
                verification_level=_analysis_step_exactness(step.status),
            )
            for step in response.analysis_steps
        ],
        warnings=response.warnings,
        unsupported_reason=response.error if status == "unsupported" else None,
        verification=evidence,
        artifacts={
            "critical_points": [point.model_dump(mode="json") for point in response.critical_points],
            "variation_table": [row.model_dump(mode="json") for row in response.variation_table],
            "asymptotes": response.asymptotes_v2,
            "graph_scene": response.graph_scene,
        },
    )


def project_geometry_solution(
    request: Any,
    response: Any,
    *,
    scene_topic: str,
) -> Solution:
    task = _geometry_task(response)
    skill_ids = skills_for_geometry_problem(scene_topic, task)
    status = _geometry_status(response)
    exactness: Exactness = "symbolic_checked" if response.confidence == "verified" and response.method == "classical" else "numeric_checked" if response.confidence == "verified" else "partial"
    verifier_methods = geometry_verifier_methods(task, skill_ids)
    evidence = []
    if response.confidence == "verified":
        evidence.append(
            VerificationEvidence(
                policy_methods=verifier_methods,
                status="pass",
                method=(
                    verifier_methods[0]
                    if task in {"pythagoras", "triangle_congruence", "triangle_similarity", "quadrilateral_metric", "circle_metric"} and verifier_methods
                    else "theorem_replay" if response.method == "classical" else "geometry_residual"
                ),
                detail=f"Geometry solver báo {response.confidence} bằng phương pháp {response.method}.",
            )
        )

    problem = ProblemEnvelope(
        domain="geometry",
        task=task,
        source=ProblemSource(
            kind="scene",
            original=request.question,
            canonical=response.question,
            provenance={"scene_id": request.scene_ref.scene_id, "revision": request.scene_ref.revision},
        ),
        curriculum=_curriculum_reference(skill_ids),
        input=GeometrySceneProblemInput(
            scene_id=request.scene_ref.scene_id,
            revision=request.scene_ref.revision,
            scene_topic=scene_topic,
            method=response.method,
        ),
        goal=response.question,
        givens=[fact.get("text", "") for fact in response.used_facts if fact.get("text")],
        constraints=response.data_issues,
    )
    steps = [_geometry_step(step, f"geometry-step-{index}", index, exactness) for index, step in enumerate(response.steps, 1)]
    claims = [
        SolutionClaim(
            claim_id=step.step_id,
            statement=legacy.claim,
            dependencies=legacy.depends_on,
            verification_level=step.verification_level,
        )
        for legacy, step in zip(response.steps, steps)
        if legacy.claim
    ]
    return Solution(
        capability_version=CAPABILITY_VERSION,
        capability=resolve_problem_capabilities(problem),
        problem=problem,
        status=status,
        exactness=exactness,
        result=SolutionValue(text=response.answer) if response.answer else None,
        steps=steps,
        claims=claims,
        warnings=[*response.warnings, *response.data_issues],
        unsupported_reason=response.answer if status == "unsupported" else None,
        verification=evidence,
        artifacts={"used_theorems": response.used_theorems, "used_facts": response.used_facts},
    )


def _curriculum_reference(skill_ids: Iterable[str]) -> CurriculumReference:
    ids = list(dict.fromkeys(skill_ids))
    grades = [grade for skill_id in ids for grade in SKILLS[skill_id].grades]
    return CurriculumReference(
        version=CURRICULUM_VERSION,
        skill_ids=ids,
        grade_min=min(grades) if grades else None,
        grade_max=max(grades) if grades else None,
    )


def _verification_policy_methods(skill_ids: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(method for skill_id in skill_ids for method in SKILLS[skill_id].verification.methods))


def _algebra_status(response: AlgebraSolveResponse) -> SolutionStatus:
    if response.problem_type == "timeout" or any("TIMEOUT" in error.upper() for error in response.errors):
        return "timeout"
    if response.status == "unsupported":
        return "unsupported"
    if response.status == "error":
        return "invalid"
    if response.status == "solved" and response.verification.status == "verified":
        return "solved_verified"
    return "solved_partial"


def _algebra_exactness(response: AlgebraSolveResponse) -> Exactness:
    return _verification_exactness(response.verification.status)


def _verification_exactness(status: str | None) -> Exactness:
    if status == "verified":
        return "symbolic_checked"
    if status == "partially_verified":
        return "partial"
    return "unverified"


def _check_status(status: str) -> str:
    return {"pass": "pass", "fail": "fail", "warn": "warn", "skip": "skip", "unknown": "skip"}.get(status, "skip")


def _algebra_source_kind(response: AlgebraSolveResponse) -> str:
    source = response.input_interpretation.source if response.input_interpretation else "raw"
    return "mathlive" if source == "structured_ui" else "api"


def _algebra_constraints(request: AlgebraSolveRequest) -> list[str]:
    constraints = [f"domain={request.domain}", f"angle_unit={request.angle_unit}"]
    if request.interval:
        constraints.append(f"interval={request.interval.model_dump(mode='json')}")
    return constraints


def _algebra_step(step: Any, step_id: str, order: int) -> SolutionStep:
    return SolutionStep(
        step_id=step_id,
        order=order,
        title=step.title,
        explanation=step.explanation,
        rule=step.rule or step.method,
        before=step.before_latex or step.expression_latex or step.expression,
        after=step.after_latex or step.result_latex or step.result,
        result=SolutionValue(text=step.result or step.explanation, latex=step.result_latex) if step.result or step.result_latex else None,
        verification_level=_algebra_step_exactness(step.confidence),
    )


def _algebra_step_exactness(confidence: str | None) -> Exactness:
    return {
        "verified": "symbolic_checked",
        "symbolic": "symbolic_checked",
        "numeric_checked": "numeric_checked",
    }.get(confidence, "unverified")


def _function_status(response: AnalyzeResponse) -> SolutionStatus:
    if response.error:
        return "invalid"
    if response.requires_parameter_confirmation:
        return "needs_clarification"
    if response.verification and response.verification.status == "verified":
        return "solved_verified"
    return "solved_partial"


def _requested_function_analyses(request: AnalyzeRequest | AnalyzerBaseRequest) -> list[str]:
    analyses = ["analyze"]
    for field in ("interval", "line", "parameter_conditions", "transform"):
        if getattr(request, field, None) is not None:
            analyses.append(field)
    return analyses


def _function_constraints(request: AnalyzeRequest | AnalyzerBaseRequest) -> list[str]:
    constraints = []
    if request.parameter_mode:
        constraints.append(f"parameter_mode={request.parameter_mode}")
    return constraints


def _analysis_step_exactness(status: str) -> Exactness:
    return "symbolic_checked" if status == "complete" else "partial" if status == "partial" else "unverified"


def _geometry_task(response: Any) -> str:
    supported = {"distance", "angle", "area", "perimeter", "pythagoras", "triangle_congruence", "triangle_similarity", "quadrilateral_metric", "circle_metric", "volume", "proof", "relation", "equation", "projection", "reflection", "intersection", "vector"}
    step_task = {
        "pythagoras_length": "pythagoras",
        "perimeter_polygon": "perimeter",
        "triangle_congruence_sss": "triangle_congruence",
        "triangle_similarity_aa": "triangle_similarity",
        "quadrilateral_metric": "quadrilateral_metric",
        "circle_metric": "circle_metric",
    }
    for step in response.steps:
        if step.kind in step_task:
            return step_task[step.kind]
        if step.kind in supported:
            return step.kind
    text = f"{response.question} {response.answer}".lower()
    markers = {
        "distance": ("khoảng cách", "distance", "d("),
        "angle": ("góc", "angle"),
        "circle_metric": ("hình tròn", "đường tròn", "circle"),
        "quadrilateral_metric": ("hình chữ nhật", "hình vuông", "hình bình hành", "hình thang", "rectangle", "square", "parallelogram", "trapezoid"),
        "area": ("diện tích", "area", "s("),
        "perimeter": ("chu vi", "perimeter", "p("),
        "pythagoras": ("pythagor", "pi-ta-go", "tính cạnh", "tìm cạnh"),
        "triangle_congruence": ("bằng nhau", "congruent", "≅", "≡"),
        "triangle_similarity": ("đồng dạng", "similar", "∼"),
        "volume": ("thể tích", "volume", "v("),
        "equation": ("phương trình", "equation"),
        "projection": ("hình chiếu", "projection"),
        "reflection": ("đối xứng", "reflection"),
        "intersection": ("giao điểm", "intersection"),
        "vector": ("vector", "vectơ"),
    }
    return next((task for task, terms in markers.items() if any(term in text for term in terms)), "relation")


def _geometry_status(response: Any) -> SolutionStatus:
    if response.confidence == "insufficient" or not response.steps:
        return "unsupported"
    if response.confidence == "verified":
        return "solved_verified"
    return "solved_partial"


def _geometry_step(step: Any, step_id: str, order: int, exactness: Exactness) -> SolutionStep:
    return SolutionStep(
        step_id=step_id,
        order=order,
        title=step.title,
        explanation=step.explanation,
        rule=step.theorem_id or step.theorem,
        before=step.formula_latex or step.expression,
        after=step.result_latex or step.result,
        result=SolutionValue(text=step.result, latex=step.result_latex) if step.result else None,
        dependencies=step.depends_on,
        verification_level=exactness,
    )