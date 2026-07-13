from __future__ import annotations

from collections import Counter
from types import MappingProxyType
from typing import Literal

from app.math_curriculum.models import CurriculumSkill, Grade, MathStrand, SkillStatus, VerificationPolicy

CURRICULUM_VERSION = "vn-k12-math-v1"
CAPABILITY_REGISTRY_VERSION = f"{CURRICULUM_VERSION}-capabilities-v1"


def _policy(
    *methods: str,
    exactness: Literal["exact", "symbolic_checked", "numeric_checked", "partial"] = "symbolic_checked",
) -> VerificationPolicy:
    return VerificationPolicy(methods=tuple(methods), minimum_exactness=exactness)


def _skill(
    skill_id: str,
    grades: tuple[Grade, ...],
    strand: MathStrand,
    topic: str,
    name_vi: str,
    forms: tuple[str, ...],
    *,
    status: SkillStatus = "planned",
    engines: tuple[str, ...] = (),
    prerequisites: tuple[str, ...] = (),
    policy: VerificationPolicy | None = None,
) -> CurriculumSkill:
    return CurriculumSkill(
        skill_id=skill_id,
        grades=grades,
        strand=strand,
        topic=topic,
        name_vi=name_vi,
        problem_forms=forms,
        prerequisites=prerequisites,
        verification=policy or _policy("independent_recompute"),
        status=status,
        current_engines=engines,
    )


_SKILLS = (
    _skill("number.integer_arithmetic", (6,), MathStrand.NUMBER, "integers", "Số nguyên và phép tính", ("evaluate", "compare", "word_problem")),
    _skill("number.rational_arithmetic", (6, 7), MathStrand.NUMBER, "rational_numbers", "Phân số và số hữu tỉ", ("evaluate", "compare", "word_problem"), status="partial", engines=("expression_solver",)),
    _skill("number.divisibility", (6,), MathStrand.NUMBER, "divisibility", "Chia hết, UCLN và BCNN", ("prove", "compute", "word_problem")),
    _skill("number.ratio_percent", (6, 7), MathStrand.NUMBER, "ratio_percent", "Tỉ số, tỉ lệ và phần trăm", ("compute", "proportion", "word_problem")),
    _skill("algebra.expression_transform", (6, 7, 8), MathStrand.ALGEBRA, "expressions", "Thu gọn, khai triển và phân tích biểu thức", ("simplify", "expand", "factor"), status="partial", engines=("expression_solver",), policy=_policy("symbolic_equivalence")),
    _skill("algebra.polynomial_operations", (7, 8), MathStrand.ALGEBRA, "polynomials", "Phép toán đa thức", ("add", "subtract", "multiply", "divide", "factor"), status="partial", engines=("expression_solver",), prerequisites=("algebra.expression_transform",)),
    _skill("algebra.linear_equation", (6, 7, 8), MathStrand.ALGEBRA, "equation", "Phương trình bậc nhất", ("solve", "word_problem"), status="supported", engines=("equation_solver",), policy=_policy("substitution", "symbolic_equivalence")),
    _skill("algebra.linear_inequality", (8, 9), MathStrand.ALGEBRA, "inequality", "Bất phương trình bậc nhất", ("solve", "interval_solution"), status="supported", engines=("inequality_solver",), policy=_policy("interval_sampling", "symbolic_equivalence")),
    _skill("algebra.linear_system", (8, 9, 10), MathStrand.ALGEBRA, "system", "Hệ phương trình tuyến tính", ("solve_2_variables", "solve_3_variables", "word_problem"), status="supported", engines=("system_solver",), policy=_policy("relation_substitution")),
    _skill("algebra.absolute_radical", (8, 9), MathStrand.ALGEBRA, "absolute_radical", "Giá trị tuyệt đối và căn thức", ("simplify", "equation", "inequality"), status="partial", engines=("equation_solver", "inequality_solver")),
    _skill("function.linear_quadratic", (9, 10), MathStrand.FUNCTION, "elementary_functions", "Hàm bậc nhất và bậc hai", ("evaluate", "graph", "variation", "roots"), status="partial", engines=("function_analyzer", "equation_solver")),
    _skill("geometry.basic_measurement", (6, 7), MathStrand.GEOMETRY, "measurement", "Góc, chu vi và diện tích cơ bản", ("angle", "perimeter", "area"), status="partial", engines=("geometry_engine",)),
    _skill("geometry.triangle_congruence", (7, 8), MathStrand.GEOMETRY, "triangles", "Tam giác và các trường hợp bằng nhau", ("prove_congruence", "derive_length", "derive_angle")),
    _skill("geometry.similarity_pythagoras", (8, 9), MathStrand.GEOMETRY, "triangle_similarity", "Đồng dạng và định lý Pythagore", ("prove_similarity", "length", "ratio"), status="partial", engines=("geometry_engine", "classical_proof")),
    _skill("geometry.quadrilateral", (8, 9), MathStrand.GEOMETRY, "quadrilaterals", "Tứ giác đặc biệt", ("classify", "prove_relation", "metric")),
    _skill("geometry.circle_basic", (9,), MathStrand.GEOMETRY, "circle", "Đường tròn cơ bản", ("central_angle", "inscribed_angle", "tangent", "chord"), status="partial", engines=("geometry_kernel",)),
    _skill("statistics.descriptive_raw", (7, 8, 10), MathStrand.STATISTICS, "descriptive_statistics", "Thống kê mô tả dữ liệu thô", ("mean", "median", "mode", "variance", "standard_deviation"), status="partial", engines=("statistics_solver",)),
    _skill("probability.classical", (8, 9, 10), MathStrand.PROBABILITY, "classical_probability", "Xác suất cổ điển", ("sample_space", "event", "compute"), status="partial", engines=("combinatorics_probability_solver",)),
    _skill("algebra.quadratic_equation", (9, 10), MathStrand.ALGEBRA, "equation", "Phương trình bậc hai", ("solve", "viete", "parameter"), status="supported", engines=("equation_solver", "parameter_solver"), policy=_policy("substitution", "viete_recompute")),
    _skill("algebra.polynomial_rational_equation", (9, 10, 11), MathStrand.ALGEBRA, "equation", "Phương trình đa thức và hữu tỉ", ("solve", "domain", "extraneous_roots"), status="partial", engines=("equation_solver",)),
    _skill("algebra.nonlinear_system", (9, 10), MathStrand.ALGEBRA, "system", "Hệ phương trình phi tuyến", ("solve", "parameter"), status="partial", engines=("system_solver",)),
    _skill("function.analysis", (10, 11, 12), MathStrand.FUNCTION, "function_analysis", "Khảo sát và đồ thị hàm số", ("domain", "range", "variation", "extrema", "asymptotes", "graph"), status="supported", engines=("function_analyzer",), policy=_policy("symbolic_recompute", "numeric_sampling")),
    _skill("algebra.trigonometry", (10, 11), MathStrand.ALGEBRA, "trigonometry", "Công thức và phương trình lượng giác", ("transform", "solve_equation", "interval_solution"), status="supported", engines=("trig_solver",)),
    _skill("algebra.sequence", (11,), MathStrand.ALGEBRA, "sequence", "Dãy số, cấp số cộng và cấp số nhân", ("term", "sum", "identify"), status="supported", engines=("sequence_solver",)),
    _skill("geometry.coordinate_2d", (10,), MathStrand.GEOMETRY, "coordinate_2d", "Vector và tọa độ trong mặt phẳng", ("vector", "line", "circle", "distance", "angle"), status="partial", engines=("geometry_engine", "function_analyzer")),
    _skill("combinatorics.counting", (10, 11), MathStrand.PROBABILITY, "combinatorics", "Quy tắc đếm, hoán vị, chỉnh hợp và tổ hợp", ("count", "permutation", "combination", "binomial"), status="partial", engines=("combinatorics_probability_solver",)),
    _skill("probability.rules", (11, 12), MathStrand.PROBABILITY, "probability_rules", "Quy tắc xác suất và biến cố", ("union", "intersection", "conditional", "independence", "bayes"), status="partial", engines=("combinatorics_probability_solver",)),
    _skill("algebra.exponential_logarithm", (11, 12), MathStrand.ALGEBRA, "exponential_log", "Mũ và logarit", ("transform", "equation", "inequality"), status="supported", engines=("exp_log_solver",)),
    _skill("calculus.limit_continuity", (11, 12), MathStrand.CALCULUS, "limit", "Giới hạn và liên tục", ("finite_limit", "one_sided", "infinite", "continuity"), status="partial", engines=("calculus_solver",)),
    _skill("calculus.derivative", (11, 12), MathStrand.CALCULUS, "derivative", "Đạo hàm và ứng dụng", ("differentiate", "tangent", "monotonicity", "extrema", "optimization"), status="partial", engines=("calculus_solver", "function_analyzer"), policy=_policy("differentiate_back", "finite_difference")),
    _skill("calculus.integral", (12,), MathStrand.CALCULUS, "integral", "Nguyên hàm, tích phân và diện tích", ("antiderivative", "definite_integral", "area"), status="partial", engines=("calculus_solver",), policy=_policy("differentiate_back", "newton_leibniz")),
    _skill("algebra.complex_numbers", (12,), MathStrand.ALGEBRA, "complex", "Số phức", ("arithmetic", "modulus", "argument", "equation"), status="partial", engines=("complex_solver",)),
    _skill("algebra.parameter", (10, 11, 12), MathStrand.ALGEBRA, "parameter", "Bài toán tham số", ("root_count", "root_relation", "extrema_condition"), status="partial", engines=("parameter_solver",)),
    _skill("statistics.grouped_data", (10, 11, 12), MathStrand.STATISTICS, "grouped_statistics", "Mẫu số liệu ghép nhóm", ("mean", "quartiles", "variance", "outliers"), status="planned"),
    _skill("geometry.solid_relations", (11,), MathStrand.GEOMETRY, "solid_geometry", "Quan hệ song song và vuông góc trong không gian", ("prove_parallel", "prove_perpendicular", "angle"), status="partial", engines=("classical_proof", "geometry_kernel")),
    _skill("geometry.solid_metric", (11, 12), MathStrand.GEOMETRY, "solid_geometry", "Khoảng cách, góc và thể tích không gian", ("distance", "angle", "area", "volume"), status="supported", engines=("solver_service", "geometry_engine"), policy=_policy("geometry_residual", "cross_check")),
    _skill("geometry.coordinate_3d", (12,), MathStrand.GEOMETRY, "coordinate_3d", "Tọa độ Oxyz", ("vector", "line", "plane", "sphere", "distance", "angle", "intersection"), status="partial", engines=("solver_service", "geometry_engine", "geometry_kernel")),
)

SKILLS = MappingProxyType({skill.skill_id: skill for skill in _SKILLS})

ALGEBRA_TOPIC_SKILLS = MappingProxyType({
    "equation": ("algebra.linear_equation", "algebra.quadratic_equation", "algebra.polynomial_rational_equation"),
    "inequality": ("algebra.linear_inequality", "algebra.absolute_radical"),
    "exponential_log": ("algebra.exponential_logarithm",),
    "trigonometry": ("algebra.trigonometry",),
    "complex": ("algebra.complex_numbers",),
    "system": ("algebra.linear_system", "algebra.nonlinear_system"),
    "sequence": ("algebra.sequence",),
    "combinatorics_probability": ("combinatorics.counting", "probability.classical", "probability.rules"),
    "statistics": ("statistics.descriptive_raw", "statistics.grouped_data"),
    "parameter": ("algebra.parameter",),
    "calculus_derivative": ("calculus.derivative",),
    "calculus_derivative_by_definition": ("calculus.derivative",),
    "calculus_continuous_at": ("calculus.limit_continuity",),
    "calculus_limit": ("calculus.limit_continuity",),
    "calculus_integral": ("calculus.integral",),
})

FUNCTION_TASK_SKILLS = MappingProxyType({
    "analyze": ("function.analysis",),
    "plot": ("function.analysis",),
    "extrema": ("function.analysis", "calculus.derivative"),
    "asymptotes": ("function.analysis", "calculus.limit_continuity"),
})

RENDER_TOPIC_SKILLS = MappingProxyType({
    "function_graph": ("function.analysis",),
    "conic": ("geometry.circle_basic", "geometry.coordinate_2d"),
    "coordinate_2d": ("geometry.coordinate_2d",),
    "coordinate_3d": ("geometry.coordinate_3d",),
    "solid_geometry": ("geometry.solid_relations", "geometry.solid_metric"),
})

GEOMETRY_TASK_SKILLS = MappingProxyType({
    "distance": ("geometry.basic_measurement", "geometry.solid_metric", "geometry.coordinate_2d", "geometry.coordinate_3d"),
    "angle": ("geometry.basic_measurement", "geometry.solid_metric", "geometry.coordinate_2d", "geometry.coordinate_3d"),
    "area": ("geometry.basic_measurement", "geometry.solid_metric"),
    "volume": ("geometry.solid_metric",),
    "proof": ("geometry.triangle_congruence", "geometry.similarity_pythagoras", "geometry.solid_relations"),
    "relation": ("geometry.quadrilateral", "geometry.circle_basic", "geometry.solid_relations"),
    "equation": ("geometry.coordinate_2d", "geometry.coordinate_3d"),
    "projection": ("geometry.coordinate_2d", "geometry.coordinate_3d"),
    "reflection": ("geometry.coordinate_2d", "geometry.coordinate_3d"),
    "intersection": ("geometry.coordinate_2d", "geometry.coordinate_3d"),
    "vector": ("geometry.coordinate_2d", "geometry.coordinate_3d"),
})


def registry_snapshot() -> dict[str, object]:
    status_counts = Counter(skill.status for skill in SKILLS.values())
    return {
        "version": CURRICULUM_VERSION,
        "grades": list(range(6, 13)),
        "status_counts": dict(sorted(status_counts.items())),
        "skills": [skill.to_dict() for skill in SKILLS.values()],
    }


def skills_for_grade(grade: Grade) -> tuple[CurriculumSkill, ...]:
    return tuple(skill for skill in SKILLS.values() if grade in skill.grades)


def skills_for_legacy_intent(target: str, topic: str, task: str) -> tuple[str, ...]:
    if target == "algebra":
        return ALGEBRA_TOPIC_SKILLS.get(topic, ())
    if target == "analyzer":
        return FUNCTION_TASK_SKILLS.get(task, ())
    if target == "render":
        return RENDER_TOPIC_SKILLS.get(topic, ())
    if target == "geometry_solve":
        return GEOMETRY_TASK_SKILLS.get(task, ())
    if target == "ocr":
        return (
            ALGEBRA_TOPIC_SKILLS.get(topic)
            or FUNCTION_TASK_SKILLS.get(task)
            or RENDER_TOPIC_SKILLS.get(topic)
            or ()
        )
    return ()