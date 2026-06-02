import pytest

from app.schemas.algebra import (
    AlgebraSolutionSet,
    AlgebraSolveResponse,
    AlgebraSolveStep,
    AlgebraVerificationReport,
)
from app.services.algebra import ai_explainer


@pytest.mark.anyio
async def test_ai_explainer_only_rewrites_safe_language_fields(monkeypatch):
    response = AlgebraSolveResponse(
        input="x^2-1=0",
        normalized_input="x**2-1=0",
        topic="equation",
        problem_type="solve_equation",
        status="solved",
        answer="Tập nghiệm: {-1; 1}",
        answer_latex=r"\left\{-1, 1\right\}",
        solution_set=AlgebraSolutionSet(kind="finite", text="Tập nghiệm: {-1; 1}", latex=r"\left\{-1, 1\right\}"),
        verification=AlgebraVerificationReport(status="verified"),
        steps=[
            AlgebraSolveStep(
                index=1,
                title="Old title",
                explanation="Old explanation",
                goal="Old goal",
                why="Old why",
                rule="Old rule",
                operation="Old operation",
                before_latex="x^2-1=0",
                after_latex=r"x=\pm 1",
                pitfall="Old pitfall",
                check="Old check",
                expression_latex="x^2-1",
                result_latex=r"\left\{-1, 1\right\}",
                kind="solve",
                confidence="verified",
            )
        ],
    )

    async def fake_call_explainer(payload, settings):
        return {
            "steps": [
                {
                    "index": 1,
                    "title": "New title",
                    "explanation": "New explanation",
                    "goal": "New goal",
                    "why": "New why",
                    "rule": "New rule",
                    "operation": "New operation",
                    "before_latex": "tampered",
                    "after_latex": "tampered",
                    "expression_latex": "tampered",
                    "result_latex": "tampered",
                    "pitfall": "New pitfall",
                    "check": "New check",
                }
            ]
        }

    monkeypatch.setattr(ai_explainer, "_call_explainer", fake_call_explainer)

    explained = await ai_explainer.explain_algebra_response_with_ai(response, object())
    step = explained.steps[0]

    assert step.title == "New title"
    assert step.goal == "New goal"
    assert step.why == "New why"
    assert step.rule == "New rule"
    assert step.operation == "New operation"
    assert step.pitfall == "New pitfall"
    assert step.check == "New check"
    assert step.before_latex == "x^2-1=0"
    assert step.after_latex == r"x=\pm 1"
    assert step.expression_latex == "x^2-1"
    assert step.result_latex == r"\left\{-1, 1\right\}"
