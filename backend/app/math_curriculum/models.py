from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal


Grade = Literal[6, 7, 8, 9, 10, 11, 12]
SkillStatus = Literal["supported", "partial", "planned", "unsupported"]


class MathStrand(StrEnum):
    NUMBER = "number"
    ALGEBRA = "algebra"
    FUNCTION = "function"
    GEOMETRY = "geometry"
    PROBABILITY = "probability"
    STATISTICS = "statistics"
    CALCULUS = "calculus"


@dataclass(frozen=True)
class VerificationPolicy:
    methods: tuple[str, ...]
    minimum_exactness: Literal["exact", "symbolic_checked", "numeric_checked", "partial"]


@dataclass(frozen=True)
class CurriculumSkill:
    skill_id: str
    grades: tuple[Grade, ...]
    strand: MathStrand
    topic: str
    name_vi: str
    problem_forms: tuple[str, ...]
    prerequisites: tuple[str, ...]
    verification: VerificationPolicy
    status: SkillStatus
    current_engines: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "skill_id": self.skill_id,
            "grades": list(self.grades),
            "strand": self.strand.value,
            "topic": self.topic,
            "name_vi": self.name_vi,
            "problem_forms": list(self.problem_forms),
            "prerequisites": list(self.prerequisites),
            "verification": {
                "methods": list(self.verification.methods),
                "minimum_exactness": self.verification.minimum_exactness,
            },
            "status": self.status,
            "current_engines": list(self.current_engines),
        }