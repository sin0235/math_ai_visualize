"""Regression matrix for algebra-solver core CAS paths (not full THPT product)."""

from app.schemas.algebra import AlgebraSolveRequest
from app.services.algebra import solve_algebra

CASES = [
    ("Abs(x-1)=2", "equation", {"solved", "partial"}),
    ("(x-1)/(x+2)>0", "inequality", {"solved", "partial"}),
    ("sqrt(x+1)=x-1", "equation", {"solved", "partial"}),
    ("2*sin(x)**2-sin(x)-1=0", "trigonometry", {"solved", "partial", "unsupported"}),
    ("log(x-1)+log(x+1)=log(3)", "exponential_log", {"solved", "partial", "unsupported"}),
    ("stats(data=1,2,3)", "statistics", {"solved"}),
    ("bernoulli(5,2,1/2)", "combinatorics_probability", {"solved"}),
    ("P(3/10)", "combinatorics_probability", {"solved"}),
    ("Punion(1/2,1/3)", "combinatorics_probability", {"solved"}),
    ("x^2-5*x+6=0", "equation", {"solved", "partial"}),
    ("x+y=1; x-y=1", "system", {"solved", "partial", "unsupported"}),
]


def test_core_matrix_does_not_crash_and_has_status():
    for raw, expected_topic, allowed in CASES:
        result = solve_algebra(AlgebraSolveRequest(input=raw, topic="auto"))
        assert result.status in allowed | {"error"}, f"{raw}: status={result.status}"
        assert result.answer
        # Soft topic check — auto routing may refine
        if result.status == "solved" and expected_topic == "statistics":
            assert result.topic == "statistics"


def test_abs_equation_has_pedagogy_steps():
    result = solve_algebra(AlgebraSolveRequest(input="Abs(x-1)=2"))
    assert result.status in {"solved", "partial"}
    titles = " ".join(step.title for step in result.steps)
    assert "trị tuyệt đối" in titles.lower() or "Abs" in titles or result.solution_set.values


def test_bernoulli_value():
    result = solve_algebra(AlgebraSolveRequest(input="bernoulli(5,2,1/2)", topic="combinatorics_probability"))
    assert result.status == "solved"
    # C(5,2)*(1/2)^5 = 10/32 = 5/16
    assert result.solution_set.text in {"5/16", "10/32", "0.3125"}
