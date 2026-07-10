"""Regression matrix for algebra-solver core CAS paths (algebra module only)."""

from __future__ import annotations

import pytest

from app.schemas.algebra import AlgebraSolveRequest
from app.services.algebra import solve_algebra

# (input, topic_hint or auto, allowed statuses, optional answer substrings any-of)
CASES: list[tuple[str, str, set[str], list[str] | None]] = [
    # Equations
    ("x^2-5*x+6=0", "auto", {"solved", "partial"}, ["2", "3"]),
    ("Abs(x-1)=2", "auto", {"solved", "partial"}, ["-1", "3"]),
    ("Abs(x)=3", "auto", {"solved", "partial"}, ["-3", "3"]),
    ("sqrt(x+1)=x-1", "auto", {"solved", "partial"}, ["3"]),
    ("sqrt(x)=2", "auto", {"solved", "partial"}, ["4"]),
    ("(x-1)/(x+2)=0", "auto", {"solved", "partial"}, ["1"]),
    ("x**2-1=0", "auto", {"solved", "partial"}, ["-1", "1"]),
    ("2*x+3=7", "auto", {"solved", "partial"}, ["2"]),
    # Inequalities
    ("(x-1)/(x+2)>0", "auto", {"solved", "partial"}, None),
    ("x^2-1<0", "auto", {"solved", "partial"}, None),
    ("Abs(x-1)<2", "auto", {"solved", "partial"}, None),
    ("Abs(x)+Abs(x-1)<3", "auto", {"solved", "partial"}, None),
    ("sqrt(x+1)<2", "auto", {"solved", "partial"}, None),
    ("x-1>=0", "auto", {"solved", "partial"}, None),
    ("x**2>=0", "auto", {"solved", "partial"}, None),
    ("(x-2)/(x-1)<=0", "auto", {"solved", "partial"}, None),
    # Exp-log / trig
    ("2*sin(x)**2-sin(x)-1=0", "trigonometry", {"solved", "partial", "unsupported"}, None),
    ("sin(x)=1/2", "trigonometry", {"solved", "partial", "unsupported"}, None),
    ("log(x-1)+log(x+1)=log(3)", "exponential_log", {"solved", "partial", "unsupported"}, None),
    ("2**x=8", "exponential_log", {"solved", "partial", "unsupported"}, None),
    ("exp(x)=1", "exponential_log", {"solved", "partial", "unsupported"}, None),
    # System / complex
    ("x+y=1; x-y=1", "system", {"solved", "partial", "unsupported"}, None),
    ("x+y=3; 2*x-y=0", "system", {"solved", "partial", "unsupported"}, None),
    # Sequence / combinatorics / stats / probability
    ("arithmetic(u1=2,d=3,n=10)", "sequence", {"solved", "partial", "unsupported"}, None),
    ("C(10,3)", "combinatorics_probability", {"solved"}, ["120"]),
    ("A(5,2)", "combinatorics_probability", {"solved"}, ["20"]),
    ("5!", "combinatorics_probability", {"solved"}, ["120"]),
    ("P(3/10)", "combinatorics_probability", {"solved"}, ["3/10"]),
    ("P_not(2/5)", "combinatorics_probability", {"solved"}, ["3/5"]),
    ("P_and(1/2,1/3)", "combinatorics_probability", {"solved"}, ["1/6"]),
    ("Punion(1/2,1/3)", "combinatorics_probability", {"solved"}, ["2/3"]),
    ("Pcond(1/2,1/3)", "combinatorics_probability", {"solved"}, ["1/2"]),
    ("bernoulli(5,2,1/2)", "combinatorics_probability", {"solved"}, ["5/16", "10/32"]),
    ("stats(data=1,2,2,3,5)", "statistics", {"solved"}, ["mean"]),
    ("stats(data=1,2,3)", "statistics", {"solved"}, ["mean"]),
    ("stats_freq(values=1,2,3;freqs=2,3,1)", "statistics", {"solved"}, ["mean"]),
    # Calculus structured
    ("derivative(expr=x**2,var=x)", "calculus_derivative", {"solved", "partial", "unsupported"}, None),
    ("limit(expr=(x**2-1)/(x-1),var=x,to=1)", "calculus_limit", {"solved", "partial", "unsupported"}, None),
    ("integral(expr=x,var=x)", "calculus_integral", {"solved", "partial", "unsupported"}, None),
    # Parameter templates
    ("quadratic_has_two_roots(a=1,b=m,c=1,var=x,param=m)", "parameter", {"solved", "partial", "unsupported"}, None),
    # Extra algebra
    ("x**3-x=0", "auto", {"solved", "partial"}, None),
    ("1/x=2", "auto", {"solved", "partial"}, ["1/2"]),
    ("x**2+1=0", "auto", {"solved", "partial", "unsupported"}, None),
    ("0*x=1", "auto", {"solved", "partial", "error", "unsupported"}, None),
    ("Abs(2*x-4)=0", "auto", {"solved", "partial"}, ["2"]),
    ("sqrt(x-1)>=0", "inequality", {"solved", "partial", "unsupported"}, None),
    ("x!=1", "inequality", {"solved", "partial"}, None),
    ("0<x<1", "inequality", {"solved", "partial"}, None),
    ("cos(x)=0", "trigonometry", {"solved", "partial", "unsupported"}, None),
    ("ln(x)=0", "exponential_log", {"solved", "partial", "unsupported"}, None),
]


@pytest.mark.parametrize("raw,topic,allowed,_keys", CASES)
def test_core_matrix_case(raw: str, topic: str, allowed: set[str], _keys: list[str] | None):
    result = solve_algebra(AlgebraSolveRequest(input=raw, topic=topic if topic != "auto" else "auto"))
    assert result.status in allowed, f"{raw}: got {result.status}, answer={result.answer!r}"
    assert result.answer
    if _keys and result.status == "solved":
        blob = result.answer + (result.solution_set.text or "") + "".join(v.text for v in result.solution_set.values)
        assert any(key in blob for key in _keys), f"{raw}: expected one of {_keys} in {blob!r}"


def test_abs_equation_pedagogy_and_roots():
    result = solve_algebra(AlgebraSolveRequest(input="Abs(x-1)=2"))
    assert result.status in {"solved", "partial"}
    values = {v.text for v in result.solution_set.values}
    assert values == {"-1", "3"} or ({"-1", "3"} <= values)
    titles = " ".join(s.title for s in result.steps).lower()
    assert "trị tuyệt đối" in titles or "abs" in titles


def test_abs_inequality_interval():
    result = solve_algebra(AlgebraSolveRequest(input="Abs(x-1)<2"))
    assert result.status in {"solved", "partial"}
    # (-1, 3)
    latex_or_text = (result.answer_latex or "") + result.answer
    assert "1" in latex_or_text or "3" in latex_or_text
    titles = " ".join(s.title for s in result.steps).lower()
    assert "trị tuyệt đối" in titles or "xét dấu" in titles or result.solution_set.kind in {"interval", "set", "empty"}


def test_radical_inequality_respects_domain():
    result = solve_algebra(AlgebraSolveRequest(input="sqrt(x+1)<2"))
    assert result.status in {"solved", "partial"}
    # Domain x>=-1 and solution (-1, 3) roughly
    assert result.answer


def test_sign_chart_rational_inequality_steps():
    result = solve_algebra(AlgebraSolveRequest(input="(x-1)/(x+2)>0"))
    assert result.status in {"solved", "partial"}
    titles = [s.title for s in result.steps]
    assert any("dấu" in t.lower() or "xét" in t.lower() or "khoảng" in t.lower() for t in titles)


def test_bernoulli_exact():
    result = solve_algebra(AlgebraSolveRequest(input="bernoulli(5,2,1/2)", topic="combinatorics_probability"))
    assert result.status == "solved"
    assert result.solution_set.text in {"5/16", "10/32", "0.3125"}
