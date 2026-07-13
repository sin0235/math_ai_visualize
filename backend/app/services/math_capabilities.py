from __future__ import annotations

from functools import lru_cache
from typing import Literal

from app.math_curriculum import (
    ALGEBRA_TOPIC_SKILLS,
    CAPABILITY_REGISTRY_VERSION,
    CURRICULUM_VERSION,
    SKILLS,
    skills_for_legacy_intent,
)
from app.math_curriculum.models import CurriculumSkill, SkillStatus
from app.schemas.math_capabilities import (
    AlgebraTopicCapability,
    CapabilitySnapshot,
    MathCapability,
    MathCapabilityRegistry,
    MathCapabilityUi,
)
from app.schemas.math_problem import (
    CurriculumReference,
    ExpressionProblemInput,
    FunctionAnalysisProblemInput,
    GeometrySceneProblemInput,
    ProblemEnvelope,
    ProblemSource,
)


_TOPIC_LABELS = {
    "equation": "Phương trình",
    "inequality": "Bất phương trình",
    "exponential_log": "Mũ và logarit",
    "trigonometry": "Lượng giác",
    "complex": "Số phức",
    "sequence": "Dãy số và cấp số",
    "combinatorics_probability": "Tổ hợp và xác suất",
    "statistics": "Thống kê",
    "system": "Hệ phương trình",
    "parameter": "Bài toán tham số",
    "calculus_derivative": "Đạo hàm",
    "calculus_derivative_by_definition": "Đạo hàm bằng định nghĩa",
    "calculus_limit": "Giới hạn",
    "calculus_continuous_at": "Liên tục tại điểm",
    "calculus_integral": "Tích phân",
}

_KEYBOARD_ACTIONS = {
    "algebra": [
        "frac", "nthRoot", "power", "log", "ln", "abs", "factorial", "combination", "permutation",
        "derivative", "integral", "limit", "system2", "system3", "equation", "sin", "cos", "tan", "cot",
        "asin", "acos", "atan", "acot", "gt", "lt", "ge", "le", "eq", "ne", "plus", "minus", "pm",
        "times", "divide", "pi", "e", "infty", "posInfty", "negInfty",
    ],
    "geometry": ["distance", "angle", "area", "volume", "perpendicular", "parallel"],
}

_SKILL_EXAMPLES = {
    "algebra.linear_equation": [{"label": "Phương trình bậc nhất", "input": "2*x + 3 = 7"}],
    "algebra.quadratic_equation": [{"label": "Phương trình bậc hai", "input": "x^2 - 5*x + 6 = 0"}],
    "function.analysis": [{"label": "Khảo sát hàm số", "input": "x^3 - 3*x + 2"}],
    "geometry.solid_metric": [{"label": "Khoảng cách điểm đến mặt phẳng", "input": "d(A,(BCD))"}],
    "calculus.derivative": [{"label": "Đạo hàm", "input": "derivative(x^3 - 2*x)"}],
    "calculus.integral": [{"label": "Tích phân", "input": "integral(x^2, x, 0, 1)"}],
}


def _input_kind(skill: CurriculumSkill) -> Literal["expression", "function_analysis", "geometry_scene"]:
    if skill.strand.value == "geometry":
        return "geometry_scene"
    if skill.strand.value == "function":
        return "function_analysis"
    return "expression"


def _limits(kind: str) -> dict[str, int | float | str | bool]:
    if kind == "geometry_scene":
        return {"max_input_chars": 20_000, "requires_committed_scene": True}
    if kind == "function_analysis":
        return {"max_input_chars": 1_000, "max_variables": 1, "max_parameters": 1}
    return {"max_input_chars": 2_000, "max_variables": 8, "max_parameters": 8, "max_solutions": 50}


def _topic_status(skill_ids: tuple[str, ...]) -> SkillStatus:
    statuses = {SKILLS[skill_id].status for skill_id in skill_ids}
    if statuses == {"supported"}:
        return "supported"
    if statuses & {"supported", "partial"}:
        return "partial"
    if "planned" in statuses:
        return "planned"
    return "unsupported"


@lru_cache(maxsize=1)
def math_capability_registry() -> MathCapabilityRegistry:
    capabilities = []
    for skill in SKILLS.values():
        kind = _input_kind(skill)
        capabilities.append(
            MathCapability(
                capability_id=f"math.{skill.skill_id}.v1",
                skill_id=skill.skill_id,
                strand=skill.strand.value,
                grades=list(skill.grades),
                status=skill.status,
                accepted_input_kinds=[kind],
                tasks=list(skill.problem_forms),
                solvers=list(skill.current_engines),
                verifier_methods=list(skill.verification.methods),
                minimum_exactness=skill.verification.minimum_exactness,
                limits=_limits(kind),
                examples=_SKILL_EXAMPLES.get(skill.skill_id, []),
            )
        )

    topics = [
        AlgebraTopicCapability(
            topic=topic,
            label=_TOPIC_LABELS[topic],
            skill_ids=list(skill_ids),
            status=_topic_status(skill_ids),
        )
        for topic, skill_ids in ALGEBRA_TOPIC_SKILLS.items()
    ]
    return MathCapabilityRegistry(
        version=CAPABILITY_REGISTRY_VERSION,
        curriculum_version=CURRICULUM_VERSION,
        capabilities=capabilities,
        ui=MathCapabilityUi(algebra_topics=topics, keyboard_actions=_KEYBOARD_ACTIONS),
    )


def resolve_problem_capabilities(problem: ProblemEnvelope) -> CapabilitySnapshot:
    registry = math_capability_registry()
    by_skill = {capability.skill_id: capability for capability in registry.capabilities}
    capabilities = [by_skill[skill_id] for skill_id in problem.curriculum.skill_ids if skill_id in by_skill]
    input_kind = problem.input.kind
    incompatible = [capability.skill_id for capability in capabilities if input_kind not in capability.accepted_input_kinds]
    unavailable = [capability.skill_id for capability in capabilities if capability.status in {"planned", "unsupported"}]
    accepted = bool(capabilities) and not incompatible and len(unavailable) < len(capabilities)
    reason = None
    if not capabilities:
        reason = "Không có capability ánh xạ cho Problem IR."
    elif incompatible:
        reason = f"IR kind {input_kind} không hợp lệ cho: {', '.join(incompatible)}."
    elif not accepted:
        reason = f"Capability chưa sẵn sàng: {', '.join(unavailable)}."

    return CapabilitySnapshot(
        registry_version=registry.version,
        capability_ids=[capability.capability_id for capability in capabilities],
        skill_ids=[capability.skill_id for capability in capabilities],
        statuses=[capability.status for capability in capabilities],
        accepted=accepted,
        reason=reason,
        limits=_merge_limits(capability.limits for capability in capabilities),
        verifier_methods=list(dict.fromkeys(method for capability in capabilities for method in capability.verifier_methods)),
        metadata={"input_kind": input_kind, "domain": problem.domain, "task": problem.task},
    )


def resolve_algebra_capability(
    *,
    original: str,
    canonical: str,
    topic: str,
    task: str,
    variables: list[str],
    parameters: list[str],
    domain: Literal["R", "C", "N", "Z"],
) -> CapabilitySnapshot:
    skill_ids = (
        ("algebra.expression_transform", "algebra.polynomial_operations")
        if topic == "expression"
        else skills_for_legacy_intent("algebra", topic, task)
    )
    problem = ProblemEnvelope(
        domain="algebra",
        task=task,
        source=ProblemSource(kind="api", original=original, canonical=canonical),
        curriculum=CurriculumReference(skill_ids=list(skill_ids)),
        input=ExpressionProblemInput(
            expression=canonical,
            variables=variables,
            parameters=parameters,
            domain=domain,
        ),
        goal=task,
    )
    return resolve_problem_capabilities(problem)


def resolve_function_capability(expression: str, parameters: dict[str, str | float | None]) -> CapabilitySnapshot:
    skill_ids = skills_for_legacy_intent("analyzer", "function_analysis", "analyze")
    problem = ProblemEnvelope(
        domain="function",
        task="analyze",
        source=ProblemSource(kind="api", original=expression, canonical=expression),
        curriculum=CurriculumReference(skill_ids=list(skill_ids)),
        input=FunctionAnalysisProblemInput(expression=expression, parameters=parameters),
        goal="Khảo sát hàm số",
    )
    return resolve_problem_capabilities(problem)


def infer_geometry_task(question: str) -> str:
    text = question.lower()
    markers = {
        "distance": ("khoảng cách", "distance", "d("),
        "angle": ("góc", "angle"),
        "area": ("diện tích", "area", "s("),
        "volume": ("thể tích", "volume", "v("),
        "equation": ("phương trình", "equation"),
        "projection": ("hình chiếu", "projection"),
        "reflection": ("đối xứng", "reflection"),
        "intersection": ("giao điểm", "giao tuyến", "intersection"),
        "vector": ("vector", "vectơ"),
        "proof": ("chứng minh", "song song", "vuông góc", "parallel", "perpendicular"),
        "relation": ("thẳng hàng", "đồng phẳng", "collinear", "coplanar"),
    }
    return next((task for task, terms in markers.items() if any(term in text for term in terms)), "unknown")


def resolve_geometry_capability(
    *,
    question: str,
    task: str,
    scene_id: str,
    revision: int,
    scene_topic: str,
    method: Literal["oxyz", "classical"],
) -> CapabilitySnapshot:
    skill_ids = skills_for_legacy_intent("geometry_solve", scene_topic, task)
    problem = ProblemEnvelope(
        domain="geometry",
        task=task,
        source=ProblemSource(kind="scene", original=question, canonical=question),
        curriculum=CurriculumReference(skill_ids=list(skill_ids)),
        input=GeometrySceneProblemInput(
            scene_id=scene_id,
            revision=revision,
            scene_topic=scene_topic,
            method=method,
        ),
        goal=question,
    )
    return resolve_problem_capabilities(problem)


def _merge_limits(limit_sets) -> dict[str, int | float | str | bool]:
    merged: dict[str, int | float | str | bool] = {}
    for limits in limit_sets:
        for key, value in limits.items():
            current = merged.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and isinstance(current, (int, float)) and not isinstance(current, bool):
                merged[key] = min(current, value)
            elif current is None:
                merged[key] = value
    return merged