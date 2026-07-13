from app.main import app
from app.math_curriculum import CAPABILITY_REGISTRY_VERSION, CURRICULUM_VERSION, SKILLS
from app.schemas.algebra import AlgebraSolveRequest
from app.schemas.math_problem import (
    CurriculumReference,
    ExpressionProblemInput,
    ProblemEnvelope,
    ProblemSource,
)
from app.services.algebra.service import _preserve_explicit_request_contract
from app.services.function_analysis_capabilities import analyzer_capability_registry
from app.services.math_capabilities import (
    math_capability_registry,
    resolve_algebra_capability,
    resolve_function_capability,
    resolve_problem_capabilities,
)


def test_math_capability_registry_covers_taxonomy_and_ui_topics():
    registry = math_capability_registry()

    assert registry.version == CAPABILITY_REGISTRY_VERSION
    assert registry.curriculum_version == CURRICULUM_VERSION
    assert registry.rollout_version.endswith("-rollout-v1")
    assert {capability.skill_id for capability in registry.capabilities} == set(SKILLS)
    assert all(capability.name_vi for capability in registry.capabilities)
    assert all(
        capability.rollout_stage == ("public" if capability.status == "supported" else "internal_beta" if capability.status == "partial" else "shadow")
        for capability in registry.capabilities
    )
    assert all(capability.solvers for capability in registry.capabilities if capability.status in {"supported", "partial"})
    assert {topic.topic for topic in registry.ui.algebra_topics} == {
        "arithmetic",
        "expression",
        "equation",
        "inequality",
        "exponential_log",
        "trigonometry",
        "complex",
        "sequence",
        "combinatorics_probability",
        "statistics",
        "system",
        "parameter",
        "calculus_derivative",
        "calculus_derivative_by_definition",
        "calculus_limit",
        "calculus_continuous_at",
        "calculus_integral",
    }
    assert "derivative" in registry.ui.keyboard_actions["algebra"]


def test_capability_resolver_validates_problem_ir_kind_and_availability():
    problem = ProblemEnvelope(
        domain="algebra",
        task="solve",
        source=ProblemSource(kind="api", original="2*x=4", canonical="2*x=4"),
        curriculum=CurriculumReference(skill_ids=["algebra.linear_equation"]),
        input=ExpressionProblemInput(expression="2*x=4", variables=["x"]),
        goal="solve_equation",
    )

    snapshot = resolve_problem_capabilities(problem)

    assert snapshot.accepted is True
    assert snapshot.capability_ids == ["math.algebra.linear_equation.v1"]
    assert "substitution" in snapshot.verifier_methods
    assert snapshot.limits["max_input_chars"] == 2_000


def test_arithmetic_capability_resolves_only_selected_curriculum_skill():
    snapshot = resolve_algebra_capability(
        original="20 là bao nhiêu phần trăm của 80",
        canonical="percent_ratio(part=20,whole=80)",
        topic="arithmetic",
        task="solve",
        variables=[],
        parameters=[],
        domain="R",
    )

    assert snapshot.accepted is True
    assert snapshot.skill_ids == ["number.ratio_percent"]
    assert snapshot.capability_ids == ["math.number.ratio_percent.v1"]


def test_expression_capability_does_not_claim_polynomial_skill_for_rational_input():
    polynomial = resolve_algebra_capability(
        original="Phân tích x^2 - 1 thành nhân tử",
        canonical="x^2-1",
        topic="expression",
        task="factor",
        variables=["x"],
        parameters=[],
        domain="R",
    )
    rational = resolve_algebra_capability(
        original="Phân tích (x + 1)/(x - 1)",
        canonical="(x+1)/(x-1)",
        topic="expression",
        task="factor",
        variables=["x"],
        parameters=[],
        domain="R",
    )

    assert polynomial.skill_ids == ["algebra.expression_transform", "algebra.polynomial_operations"]
    assert rational.skill_ids == ["algebra.expression_transform"]


def test_math_capability_route_and_function_adapter_share_registry_version():
    assert "/api/math/capabilities" in app.openapi()["paths"]
    assert analyzer_capability_registry()["math_registry_version"] == CAPABILITY_REGISTRY_VERSION


def test_ai_extraction_cannot_override_explicit_problem_contract():
    original = AlgebraSolveRequest(
        input="Giải trong C phương trình z^2 + 1 = 0",
        topic="complex",
        expression_action="factor",
        variables=["z"],
        parameters=["m"],
        domain="C",
        domain_source="user",
    )
    extracted = AlgebraSolveRequest(
        input="z^2 + 1 = 0",
        topic="equation",
        expression_action="expand",
        variables=["x"],
        domain="R",
    )

    protected = _preserve_explicit_request_contract(original, extracted)

    assert protected.topic == "complex"
    assert protected.expression_action == "factor"
    assert protected.domain == "C"
    assert protected.domain_source == "user"
    assert protected.variables == ["z"]
    assert protected.parameters == ["m"]


def test_upper_secondary_capabilities_are_expression_specific():
    quadratic = resolve_algebra_capability(
        original="x^2 - 5*x + 6 = 0",
        canonical="x^2-5*x+6=0",
        topic="equation",
        task="solve",
        variables=["x"],
        parameters=[],
        domain="R",
    )
    rational = resolve_algebra_capability(
        original="(x^2 - 1)/(x - 1) = 0",
        canonical="(x^2-1)/(x-1)=0",
        topic="equation",
        task="solve",
        variables=["x"],
        parameters=[],
        domain="R",
    )
    nonlinear_system = resolve_algebra_capability(
        original="x^2+y^2=5; x-y=1",
        canonical="x^2+y^2=5;x-y=1",
        topic="system",
        task="solve",
        variables=["x", "y"],
        parameters=[],
        domain="R",
    )
    quadratic_function = resolve_function_capability("x^2-4*x+3", {})
    cubic_function = resolve_function_capability("x^3-3*x+1", {})

    assert quadratic.skill_ids == ["algebra.quadratic_equation"]
    assert rational.skill_ids == ["algebra.polynomial_rational_equation"]
    assert nonlinear_system.skill_ids == ["algebra.nonlinear_system"]
    assert quadratic_function.skill_ids == ["function.linear_quadratic"]
    assert cubic_function.skill_ids == ["function.analysis"]
