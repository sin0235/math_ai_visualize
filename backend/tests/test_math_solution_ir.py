from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.algebra import (
    AlgebraSolveRequest,
    AlgebraSolveResponse,
    AlgebraVerificationCheck,
    AlgebraVerificationReport,
)
from app.schemas.analysis import AnalyzeRequest, AnalyzeResponse, VerificationCheck, VerificationReport
from app.schemas.math_problem import CurriculumReference
from app.services.math_solution_projectors import (
    CAPABILITY_VERSION,
    project_algebra_solution,
    project_function_solution,
    project_geometry_solution,
)


def test_problem_ir_rejects_unknown_curriculum_skill():
    with pytest.raises(ValidationError, match="Skill ID không tồn tại"):
        CurriculumReference(skill_ids=["algebra.not_real"])


def test_algebra_projector_preserves_legacy_result_and_adds_verified_ir():
    request = AlgebraSolveRequest(input="x + 1 = 2", topic="equation", variables=["x"])
    response = AlgebraSolveResponse(
        input=request.input,
        normalized_input="x + 1 = 2",
        topic="equation",
        problem_type="solve_equation",
        status="solved",
        answer="x = 1",
        answer_latex="x = 1",
        verification=AlgebraVerificationReport(
            status="verified",
            checks=[AlgebraVerificationCheck(name="substitution", status="pass", detail="Thế x = 1 đúng.")],
        ),
    )

    projected = project_algebra_solution(request, response)

    assert response.answer == "x = 1"
    assert projected.status == "solved_verified"
    assert projected.problem.curriculum.skill_ids == ["algebra.linear_equation"]
    assert projected.verification[0].status == "pass"
    assert projected.capability.accepted is True
    assert projected.capability.registry_version == "vn-k12-math-v1-capabilities-v1"
    assert projected.capability_version == CAPABILITY_VERSION


def test_function_projector_maps_analysis_and_verification():
    request = AnalyzeRequest(expression="x^2")
    response = AnalyzeResponse(
        expression="x**2",
        derivative="2*x",
        domain="Reals",
        verification=VerificationReport(
            status="verified",
            checks=[VerificationCheck(name="derivative", status="pass", method="symbolic", detail="Đạo hàm khớp.")],
        ),
    )

    projected = project_function_solution(request, response)

    assert projected.status == "solved_verified"
    assert projected.problem.curriculum.skill_ids == ["function.linear_quadratic"]
    assert projected.result is not None
    assert projected.result.data["derivative"] == "2*x"
    assert projected.verification[0].method == "symbolic"


def test_geometry_projector_maps_scene_identity_claims_and_unsupported_status():
    request = SimpleNamespace(
        question="Tính thể tích khối chóp S.ABCD",
        scene_ref=SimpleNamespace(scene_id="scene-1", revision=3),
    )
    step = SimpleNamespace(
        kind="volume",
        title="Tính thể tích",
        explanation="Áp dụng công thức thể tích khối chóp.",
        theorem_id="pyramid_volume",
        theorem="Công thức thể tích khối chóp",
        formula_latex="V=\\frac13Sh",
        expression=None,
        result_latex="12",
        result="12",
        depends_on=[],
        claim="V = 12",
    )
    response = SimpleNamespace(
        question=request.question,
        answer="V = 12",
        steps=[step],
        warnings=[],
        confidence="verified",
        method="classical",
        used_facts=[{"text": "S.ABCD là khối chóp"}],
        used_theorems=[{"id": "pyramid_volume"}],
        data_issues=[],
    )

    projected = project_geometry_solution(request, response, scene_topic="solid_geometry")

    assert projected.status == "solved_verified"
    assert projected.problem.curriculum.skill_ids == ["geometry.solid_metric"]
    assert projected.problem.input.scene_id == "scene-1"
    assert projected.claims[0].statement == "V = 12"

    response.steps = []
    response.answer = "Không đủ dữ kiện"
    response.confidence = "insufficient"
    unsupported = project_geometry_solution(request, response, scene_topic="solid_geometry")
    assert unsupported.status == "unsupported"
    assert unsupported.unsupported_reason == "Không đủ dữ kiện"