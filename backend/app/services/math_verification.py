from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.math_curriculum import SKILLS
from app.schemas.math_solution import Exactness, VerificationEvidence

_EXACTNESS_RANK: dict[str, int] = {
    "unverified": 0,
    "partial": 1,
    "numeric_checked": 2,
    "symbolic_checked": 3,
    "exact": 4,
}


@dataclass(frozen=True)
class VerificationContractResult:
    accepted: bool
    policy_methods: tuple[str, ...]
    evidence_methods: tuple[str, ...]
    minimum_exactness: str
    actual_exactness: Exactness
    failures: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "accepted": self.accepted,
            "policy_methods": list(self.policy_methods),
            "evidence_methods": list(self.evidence_methods),
            "minimum_exactness": self.minimum_exactness,
            "actual_exactness": self.actual_exactness,
            "failures": list(self.failures),
        }


def evaluate_verification_contract(
    skill_ids: Iterable[str],
    exactness: Exactness,
    evidence: list[VerificationEvidence],
) -> VerificationContractResult:
    skills = [SKILLS[skill_id] for skill_id in dict.fromkeys(skill_ids) if skill_id in SKILLS]
    policy_methods = tuple(dict.fromkeys(method for skill in skills for method in skill.verification.methods))
    minimum_exactness = max(
        (skill.verification.minimum_exactness for skill in skills),
        key=lambda value: _EXACTNESS_RANK[value],
        default="partial",
    )
    failures: list[str] = []
    if not evidence or not any(item.status == "pass" for item in evidence):
        failures.append("Thiếu verification evidence đạt pass.")
    if any(item.status == "fail" for item in evidence):
        failures.append("Có verification evidence thất bại.")
    if _EXACTNESS_RANK[exactness] < _EXACTNESS_RANK[minimum_exactness]:
        failures.append(f"Exactness {exactness} thấp hơn yêu cầu {minimum_exactness}.")
    if skills and not policy_methods:
        failures.append("Capability chưa khai báo verifier policy.")
    return VerificationContractResult(
        accepted=not failures,
        policy_methods=policy_methods,
        evidence_methods=tuple(dict.fromkeys(item.method for item in evidence)),
        minimum_exactness=minimum_exactness,
        actual_exactness=exactness,
        failures=tuple(failures),
    )