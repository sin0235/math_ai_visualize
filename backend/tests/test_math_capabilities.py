from app.main import app
from app.math_curriculum import CAPABILITY_REGISTRY_VERSION, CURRICULUM_VERSION, SKILLS
from app.schemas.math_problem import (
    CurriculumReference,
    ExpressionProblemInput,
    ProblemEnvelope,
    ProblemSource,
)
from app.services.function_analysis_capabilities import analyzer_capability_registry
from app.services.math_capabilities import math_capability_registry, resolve_problem_capabilities


def test_math_capability_registry_covers_taxonomy_and_ui_topics():
    registry = math_capability_registry()

    assert registry.version == CAPABILITY_REGISTRY_VERSION
    assert registry.curriculum_version == CURRICULUM_VERSION
    assert {capability.skill_id for capability in registry.capabilities} == set(SKILLS)
    assert all(capability.solvers for capability in registry.capabilities if capability.status in {"supported", "partial"})
    assert {topic.topic for topic in registry.ui.algebra_topics} == {
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


def test_math_capability_route_and_function_adapter_share_registry_version():
    assert "/api/math/capabilities" in app.openapi()["paths"]
    assert analyzer_capability_registry()["math_registry_version"] == CAPABILITY_REGISTRY_VERSION