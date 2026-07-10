from app.schemas.algebra import AlgebraSolveRequest, AlgebraSolveResponse
from app.services.algebra.circuit_breaker import AlgebraCircuitBreaker
from app.services.algebra.cost import algebra_request_cost, cost_exceeds_limit
from app.services.algebra.pdf_export import build_algebra_pdf
from app.services.algebra import solve_algebra


def test_cost_increases_with_complexity_and_ai():
    simple = AlgebraSolveRequest(input="x-1=0")
    heavy = AlgebraSolveRequest(input="sin(x)**2+cos(x)**2+(x-1)**3+(y-2)**2=0; x+y=1", topic="system")
    from app.schemas.algebra import AlgebraSolveOptions
    ai = AlgebraSolveRequest(input="x-1=0", options=AlgebraSolveOptions(use_ai_extraction=True))
    assert algebra_request_cost(simple) < algebra_request_cost(heavy)
    assert algebra_request_cost(ai) >= algebra_request_cost(simple)
    assert cost_exceeds_limit(100, 80)
    assert not cost_exceeds_limit(10, 80)


def test_circuit_breaker_opens_after_threshold_timeouts():
    breaker = AlgebraCircuitBreaker(failure_threshold=3, window_seconds=60, open_seconds=30)
    assert breaker.allow()
    breaker.record_timeout()
    breaker.record_timeout()
    assert breaker.allow()
    breaker.record_timeout()
    assert not breaker.allow()
    assert breaker.is_open()
    breaker.reset()
    assert breaker.allow()


def test_pdf_export_starts_with_pdf_header():
    result = solve_algebra(AlgebraSolveRequest(input="x-1=0"))
    pdf = build_algebra_pdf(result)
    assert pdf[:4] == b"%PDF"


def test_probability_union_and_cond():
    union = solve_algebra(AlgebraSolveRequest(input="Punion(1/2,1/3)", topic="combinatorics_probability"))
    assert union.status == "solved"
    # 1/2 + 1/3 - 1/6 = 2/3
    assert union.solution_set.text in {"2/3", "0.6666666666666666"}
    cond = solve_algebra(AlgebraSolveRequest(input="Pcond(1/2,1/3)", topic="combinatorics_probability"))
    assert cond.status == "solved"
    assert cond.solution_set.text in {"1/2", "0.5"}
