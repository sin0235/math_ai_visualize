from __future__ import annotations

import pytest

from app.schemas.algebra import AlgebraSolveRequest
from app.services.algebra import ai_explainer
from app.services.algebra.service import solve_algebra_deterministic
from app.services.nlp.grounding import (
    LanguageRewrite,
    assert_plan_anchors_unchanged,
    build_geometry_explanation_plan,
    validate_language_rewrites,
)
from app.services.solver_explainer import explain_solver_result
from app.services.solver_service import SolverResult, SolverStep


def test_deterministic_algebra_response_contains_grounded_plan():
    response = solve_algebra_deterministic(AlgebraSolveRequest(input="x^2 - 1 = 0"))

    assert response.grounding is not None
    assert response.grounding.answer == response.answer
    assert response.grounding.answer_latex == response.answer_latex
    assert response.grounding.verification_state == response.verification.status
    assert [claim.claim_id for claim in response.grounding.claims]
    assert response.realization_status == "deterministic"


def test_language_validator_rejects_new_math_and_unknown_claim():
    response = solve_algebra_deterministic(AlgebraSolveRequest(input="x^2 - 1 = 0"))
    plan = response.grounding
    assert plan is not None
    claim_id = plan.claims[0].claim_id

    rewrites = validate_language_rewrites(
        plan,
        [
            LanguageRewrite(claim_id=claim_id, title="Giải thích rõ hơn", explanation="Có 999 nghiệm"),
            LanguageRewrite(claim_id="ghost", title="Bước mới", explanation="Nội dung mới"),
        ],
    )

    assert set(rewrites) == {claim_id}
    assert rewrites[claim_id].title == "Giải thích rõ hơn"
    assert rewrites[claim_id].explanation is None


def test_plan_anchor_invariant_detects_answer_change():
    response = solve_algebra_deterministic(AlgebraSolveRequest(input="x^2 - 1 = 0"))
    plan = response.grounding
    assert plan is not None
    changed = plan.model_copy(update={"answer": "tampered"})

    with pytest.raises(ValueError, match="grounded anchors"):
        assert_plan_anchors_unchanged(plan, changed)


@pytest.mark.anyio
async def test_algebra_ai_realization_rejects_new_numeric_claim(monkeypatch):
    response = solve_algebra_deterministic(AlgebraSolveRequest(input="x^2 - 1 = 0"))
    original_explanation = response.steps[0].explanation

    async def fake_call(_payload, _settings):
        return {
            "steps": [
                {
                    "index": response.steps[0].index,
                    "title": "Trình bày rõ hơn",
                    "explanation": "Kết quả mới là 999",
                }
            ]
        }

    monkeypatch.setattr(ai_explainer, "_call_explainer", fake_call)
    explained = await ai_explainer.explain_algebra_response_with_ai(response, object())

    assert explained.steps[0].title == "Trình bày rõ hơn"
    assert explained.steps[0].explanation == original_explanation
    assert explained.realization_status == "ai_validated"
    assert explained.grounding is not None


def _geometry_result() -> SolverResult:
    return SolverResult(
        question="Tính khoảng cách",
        answer="2",
        confidence="verified",
        warnings=[],
        steps=[
            SolverStep(
                index=1,
                title="Dữ kiện",
                explanation="Dùng dữ kiện đã kiểm chứng.",
                expression="d(A,P)",
                result="2",
                highlight=["A"],
                kind="distance_point_plane",
                formula_latex="d(A,P)",
                substitution_latex="4/2",
                result_latex="2",
                theorem="Công thức khoảng cách",
                theorem_id="distance.point_plane.perpendicular_segment",
                depends_on=["fact:A", "fact:P"],
                highlight_object_ids=["point-a", "plane-p"],
                relation_ids=["relation-a-p"],
                construction_actions=[{
                    "action_id": "action-foot",
                    "type": "highlight",
                    "source_object_ids": ["point-a", "plane-p"],
                    "parameters": {},
                }],
                sub_steps=[
                    SolverStep(
                        index=1,
                        title="Chi tiết cũ",
                        explanation="Chi tiết deterministic.",
                        expression=None,
                        result=None,
                        highlight=[],
                    )
                ],
            )
        ],
    )


@pytest.mark.anyio
async def test_geometry_ai_cannot_add_substeps_or_change_anchors(monkeypatch):
    result = _geometry_result()

    async def fake_call(*_args, **_kwargs):
        return {
            "steps": [
                {
                    "index": 1,
                    "title": "Dữ kiện rõ hơn",
                    "explanation": "Giải thích bằng lời.",
                    "formula_latex": "tampered",
                    "sub_steps": [
                        {"index": 1, "title": "Chi tiết mới", "explanation": "Diễn đạt mới."},
                        {"index": 2, "title": "Bịa thêm", "explanation": "Thêm claim."},
                    ],
                },
                {"index": 99, "title": "Bước lạ", "explanation": "Không được thêm."},
            ]
        }

    monkeypatch.setattr("app.services.solver_explainer._call_explainer", fake_call)
    explained = await explain_solver_result(result, {}, object())

    assert len(explained.steps) == 1
    assert len(explained.steps[0].sub_steps) == 1
    assert explained.steps[0].sub_steps[0].title == "Chi tiết mới"
    assert explained.steps[0].formula_latex == "d(A,P)"
    assert explained.steps[0].substitution_latex == "4/2"
    assert explained.steps[0].result_latex == "2"
    assert explained.steps[0].theorem == "Công thức khoảng cách"
    assert explained.steps[0].theorem_id == "distance.point_plane.perpendicular_segment"
    assert explained.steps[0].depends_on == ["fact:A", "fact:P"]
    assert explained.steps[0].highlight_object_ids == ["point-a", "plane-p"]
    assert explained.steps[0].relation_ids == ["relation-a-p"]
    assert explained.steps[0].construction_actions[0]["action_id"] == "action-foot"
    assert explained.confidence == "verified"
    assert explained.realization_status == "ai_validated"


@pytest.mark.anyio
async def test_geometry_ai_rejects_unknown_object_name_per_step(monkeypatch):
    result = _geometry_result()
    original_explanation = result.steps[0].explanation

    async def fake_call(*_args, **_kwargs):
        return {
            "steps": [{
                "index": 1,
                "title": "Trình bày trực quan",
                "explanation": "Gọi M là hình chiếu cần dùng.",
            }],
        }

    monkeypatch.setattr("app.services.solver_explainer._call_explainer", fake_call)
    explained = await explain_solver_result(result, {}, object(), method="classical")

    assert explained.steps[0].title == "Trình bày trực quan"
    assert explained.steps[0].explanation == original_explanation
    assert explained.realization_status == "ai_validated"


@pytest.mark.anyio
async def test_geometry_explainer_failure_does_not_lower_math_confidence(monkeypatch):
    result = _geometry_result()
    original_plan = build_geometry_explanation_plan(result)

    async def fail(*_args, **_kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr("app.services.solver_explainer._call_explainer", fail)
    explained = await explain_solver_result(result, {}, object())

    assert explained.confidence == "verified"
    assert explained.realization_status == "fallback"
    assert explained.realization_fallback_reason == "provider unavailable"
    assert explained.grounding == original_plan.model_dump(mode="json")