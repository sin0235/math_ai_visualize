from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.schemas.geometry_reasoning import (
    GeometryFact as ProofFact,
    GeometryGoal,
    GeometryProofPlan,
    GeometryProofStep,
    ProofClaim,
    VerificationEvidence,
)
from app.services.geometry_facts import GeometryFact, build_geometry_fact_graph
from app.services.geometry_theorems import THEOREMS, TheoremSpec

MAX_PROOF_STEPS = 32
MAX_PROOF_COST = 64


@dataclass(frozen=True)
class ProofReplayResult:
    accepted: bool
    plan: GeometryProofPlan | None = None
    reason: str | None = None
    cost: int = 0


def build_and_replay_proof_plan(
    scene: dict[str, Any],
    *,
    task: str,
    subtype: str,
    method: str,
    question: str,
    answer: str,
    steps: list[Any],
) -> ProofReplayResult:
    graph = build_geometry_fact_graph(scene)
    trusted = {fact.id: fact for fact in graph.facts if fact.trusted}
    proof_steps = [step for step in steps if getattr(step, "claim", None)]
    if not proof_steps:
        return ProofReplayResult(False, reason="Proof không có claim để replay.")
    if len(proof_steps) > MAX_PROOF_STEPS:
        return ProofReplayResult(False, reason=f"Proof vượt giới hạn {MAX_PROOF_STEPS} bước.")

    referenced_fact_ids = {
        dependency
        for step in proof_steps
        for dependency in getattr(step, "depends_on", [])
        if dependency in trusted
    }
    referenced_fact_ids.update(
        relation_id
        for step in proof_steps
        for relation_id in getattr(step, "relation_ids", [])
        if relation_id in trusted
    )
    referenced_facts = [trusted[fact_id] for fact_id in referenced_fact_ids]
    target_ids = list(dict.fromkeys(
        object_id
        for step in proof_steps
        for object_id in getattr(step, "highlight_object_ids", [])
    )) or list(dict.fromkeys(
        label
        for step in proof_steps
        for label in getattr(step, "highlight", [])
    ))
    goal = GeometryGoal(
        task=_schema_task(task),
        subtype=subtype or task,
        target_object_ids=target_ids or ["scene"],
        method="classical" if method == "classical" else "oxyz",
    )
    facts = [_proof_fact(fact) for fact in referenced_facts]
    known_claims: list[str] = []
    plan_steps: list[GeometryProofStep] = []
    used_claim_ids: set[str] = set()
    for index, step in enumerate(proof_steps, start=1):
        claim_id = _unique_claim_id(index, str(getattr(step, "theorem_id", "") or getattr(step, "kind", "claim")), used_claim_ids)
        fact_ids = list(dict.fromkeys(
            dependency
            for dependency in [*getattr(step, "depends_on", []), *getattr(step, "relation_ids", [])]
            if dependency in trusted
        ))
        claim_dependencies = [dependency for dependency in getattr(step, "depends_on", []) if dependency in known_claims]
        if index > 1 and not claim_dependencies:
            claim_dependencies = [known_claims[-1]]
        plan_steps.append(GeometryProofStep(
            index=index,
            title=str(step.title),
            explanation=str(step.explanation),
            claim=ProofClaim(
                claim_id=claim_id,
                text=str(step.claim),
                fact_ids=fact_ids,
                theorem_id=getattr(step, "theorem_id", None),
                depends_on=claim_dependencies,
            ),
            highlight_object_ids=list(getattr(step, "highlight_object_ids", [])),
            relation_ids=list(getattr(step, "relation_ids", [])),
            construction_actions=list(getattr(step, "construction_actions", [])),
        ))
        known_claims.append(claim_id)

    plan = GeometryProofPlan(
        goal=goal,
        facts=facts,
        steps=plan_steps,
        answer=answer,
        verification_state="verified",
    )
    replay = replay_proof_plan(plan)
    if not replay.accepted:
        return replay
    return ProofReplayResult(True, plan=plan, cost=replay.cost)


def replay_proof_plan(plan: GeometryProofPlan) -> ProofReplayResult:
    if len(plan.steps) > MAX_PROOF_STEPS:
        return ProofReplayResult(False, plan=plan, reason=f"Proof vượt giới hạn {MAX_PROOF_STEPS} bước.")

    facts = {fact.fact_id: fact for fact in plan.facts}
    known_claims: set[str] = set()
    total_cost = 0
    for step in plan.steps:
        claim = step.claim
        if any(dependency not in known_claims for dependency in claim.depends_on):
            return ProofReplayResult(False, plan=plan, reason=f"Claim {claim.claim_id} phụ thuộc claim chưa có.", cost=total_cost)
        if any(fact_id not in facts for fact_id in claim.fact_ids):
            return ProofReplayResult(False, plan=plan, reason=f"Claim {claim.claim_id} tham chiếu fact thiếu.", cost=total_cost)
        if claim.theorem_id:
            spec = THEOREMS.get(claim.theorem_id)
            if spec is None:
                return ProofReplayResult(False, plan=plan, reason=f"Theorem {claim.theorem_id} chưa đăng ký.", cost=total_cost)
            total_cost += spec.cost
            if total_cost > MAX_PROOF_COST:
                return ProofReplayResult(False, plan=plan, reason=f"Proof vượt cost {MAX_PROOF_COST}.", cost=total_cost)
            premise_facts = [facts[fact_id] for fact_id in claim.fact_ids]
            missing = _missing_premises(spec, premise_facts)
            if missing:
                return ProofReplayResult(
                    False,
                    plan=plan,
                    reason=f"Missing premise cho {claim.theorem_id}: {', '.join(missing)}.",
                    cost=total_cost,
                )
        known_claims.add(claim.claim_id)
    return ProofReplayResult(True, plan=plan, cost=total_cost)


def _missing_premises(spec: TheoremSpec, facts: list[ProofFact]) -> list[str]:
    counts: dict[str, int] = {}
    for fact in facts:
        counts[fact.type] = counts.get(fact.type, 0) + 1
    missing: list[str] = []
    for premise in spec.premises:
        accepted_types = premise.fact_type.split("|")
        actual_count = sum(counts.get(fact_type, 0) for fact_type in accepted_types)
        if actual_count < premise.min_count:
            missing.append(f"{' hoặc '.join(accepted_types)} x{premise.min_count}")
    return missing


def _proof_fact(fact: GeometryFact) -> ProofFact:
    provenance, status, verifier = _fact_verification(fact)
    return ProofFact(
        fact_id=fact.id,
        type=fact.type,
        object_ids=_fact_object_ids(fact),
        value=str(fact.args.get("label")) if fact.args.get("label") is not None else None,
        provenance=provenance,
        evidence=[VerificationEvidence(
            source=_evidence_source(fact),
            ref_id=fact.id,
            status=status,
            verifier=verifier,
            details={"source": fact.source, "text": fact.text},
        )],
    )


def _fact_verification(fact: GeometryFact) -> tuple[str, str, str | None]:
    if fact.source == "given":
        return "given", "given", None
    verifier = str(fact.metadata.get("verifier") or "") or None
    verification_kind = str(fact.metadata.get("verification_kind") or "").lower()
    if fact.verification_status == "verified" or fact.source == "verified":
        if verification_kind == "symbolic" or str(fact.metadata.get("confidence") or "").lower() == "exact":
            return "symbolically_verified", "verified", verifier or "symbolic_recompute"
        return "numerically_verified", "verified", verifier or "geometry_kernel"
    return "derived", "derived", verifier


def _fact_object_ids(fact: GeometryFact) -> list[str]:
    values: list[str] = []
    for key, value in fact.args.items():
        if key in {"label", "value", "source_ids"}:
            continue
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, tuple | list):
            values.extend(str(item) for item in value)
    return list(dict.fromkeys(values))[:12]


def _evidence_source(fact: GeometryFact) -> str:
    if fact.type in {"length", "scalar_measure", "angle_measure", "right_angle"}:
        return "annotation"
    if fact.id.startswith("derived:") or fact.type.startswith("derived_"):
        return "derived_fact"
    if fact.id.startswith("object:") or fact.type == "plane_points":
        return "object"
    return "relation"


def _unique_claim_id(index: int, raw: str, used: set[str]) -> str:
    base = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in raw).strip("-") or "claim"
    candidate = f"claim-{index}-{base}"[:128]
    suffix = 2
    while candidate in used:
        candidate = f"claim-{index}-{base}-{suffix}"[:128]
        suffix += 1
    used.add(candidate)
    return candidate


def _schema_task(task: str) -> str:
    supported = {
        "distance", "angle", "area", "perimeter", "pythagoras", "triangle_congruence",
        "triangle_similarity", "quadrilateral_metric", "circle_metric", "volume", "prove",
        "construct", "intersection", "projection", "reflection", "equation", "relation",
    }
    return task if task in supported else "relation"