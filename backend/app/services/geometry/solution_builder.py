from __future__ import annotations

from typing import Any


class SolverStep:
    def __init__(
        self,
        index: int,
        title: str,
        explanation: str,
        expression: str | None,
        result: str | None,
        highlight: list[str],
        kind: str | None = None,
        formula_latex: str | None = None,
        substitution_latex: str | None = None,
        result_latex: str | None = None,
        sub_steps: list["SolverStep"] | None = None,
        theorem: str | None = None,
        theorem_id: str | None = None,
        claim: str | None = None,
        depends_on: list[str] | None = None,
        highlight_object_ids: list[str] | None = None,
        relation_ids: list[str] | None = None,
        construction_actions: list[dict[str, Any]] | None = None,
    ) -> None:
        self.index = index
        self.title = title
        self.explanation = explanation
        self.expression = expression
        self.result = result
        self.highlight = highlight
        self.kind = kind
        self.formula_latex = formula_latex
        self.substitution_latex = substitution_latex
        self.result_latex = result_latex
        self.sub_steps = sub_steps or []
        self.theorem = theorem
        self.theorem_id = theorem_id
        self.claim = claim
        self.depends_on = depends_on or []
        self.highlight_object_ids = highlight_object_ids or []
        self.relation_ids = relation_ids or []
        self.construction_actions = construction_actions or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "title": self.title,
            "explanation": self.explanation,
            "expression": self.expression,
            "result": self.result,
            "highlight": self.highlight,
            "kind": self.kind,
            "formula_latex": self.formula_latex,
            "substitution_latex": self.substitution_latex,
            "result_latex": self.result_latex,
            "sub_steps": [step.to_dict() for step in self.sub_steps],
            "theorem": self.theorem,
            "theorem_id": self.theorem_id,
            "claim": self.claim,
            "depends_on": self.depends_on,
            "highlight_object_ids": self.highlight_object_ids,
            "relation_ids": self.relation_ids,
            "construction_actions": self.construction_actions,
        }


class SolverResult:
    def __init__(
        self,
        question: str,
        answer: str,
        steps: list[SolverStep],
        warnings: list[str],
        *,
        confidence: str = "verified",
        method: str = "oxyz",
        used_facts: list[dict[str, str]] | None = None,
        data_issues: list[str] | None = None,
        used_theorems: list[dict[str, str]] | None = None,
        proof_plan: dict[str, Any] | None = None,
        realization_status: str = "deterministic",
        realization_fallback_reason: str | None = None,
        grounding: dict[str, Any] | None = None,
    ) -> None:
        self.question = question
        self.answer = answer
        self.steps = steps
        self.warnings = warnings
        self.confidence = confidence
        self.method = method
        self.used_facts = used_facts or []
        self.data_issues = data_issues or []
        self.used_theorems = used_theorems or []
        self.proof_plan = proof_plan
        self.realization_status = realization_status
        self.realization_fallback_reason = realization_fallback_reason
        self.grounding = grounding

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "steps": [step.to_dict() for step in self.steps],
            "warnings": self.warnings,
            "confidence": self.confidence,
            "method": self.method,
            "used_facts": self.used_facts,
            "data_issues": self.data_issues,
            "used_theorems": self.used_theorems,
            "proof_plan": self.proof_plan,
            "realization_status": self.realization_status,
            "realization_fallback_reason": self.realization_fallback_reason,
            "grounding": self.grounding,
        }


def attach_replayed_proof(
    result: SolverResult,
    scene: dict[str, Any],
    task: str,
    method: str,
) -> SolverResult:
    if not result.used_theorems or result.answer in {"Không xác định", "Không đủ dữ kiện"}:
        return result
    from app.services.geometry.proof_search import build_and_replay_proof_plan

    subtype = result.steps[1].kind if len(result.steps) > 1 and result.steps[1].kind else task
    replay = build_and_replay_proof_plan(
        scene,
        task=task,
        subtype=subtype,
        method=method,
        question=result.question,
        answer=result.answer,
        steps=result.steps,
    )
    if replay.accepted and replay.plan is not None:
        result.proof_plan = replay.plan.model_dump(mode="json")
        return result
    reason = replay.reason or "Proof không replay được."
    return SolverResult(
        result.question,
        "Không đủ dữ kiện",
        [],
        [*result.warnings, reason],
        confidence="insufficient",
        method=method,
        used_facts=result.used_facts,
        data_issues=[reason],
    )