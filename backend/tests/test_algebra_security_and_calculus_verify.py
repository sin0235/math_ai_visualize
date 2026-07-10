import pytest

from app.schemas.algebra import AlgebraSolveRequest
from app.services.algebra import solve_algebra
from app.services.algebra.parser import AlgebraParseError, parse_algebra_problem


def test_parser_rejects_deeply_nested_parens():
    payload = "(" * 50 + "x" + ")" * 50
    with pytest.raises(AlgebraParseError):
        parse_algebra_problem(payload + "=0")


def test_parser_rejects_many_powers():
    payload = "x" + "^(x" * 12 + ")" * 12 + "=1"
    with pytest.raises(AlgebraParseError):
        parse_algebra_problem(payload)


def test_parser_rejects_huge_integer_token():
    with pytest.raises(AlgebraParseError):
        parse_algebra_problem("1" * 25 + "+x=0")


def test_parser_rejects_oversized_input_chars():
    with pytest.raises(AlgebraParseError):
        parse_algebra_problem("x" * 2500 + "=0")


def test_calculus_derivative_has_independent_checks():
    result = solve_algebra(AlgebraSolveRequest(input="derivative(expr=x^2,var=x)"))
    assert result.status == "solved"
    assert result.verification.status in {"verified", "partially_verified"}
    names = {check.name for check in result.verification.checks}
    assert "derivative_recompute" in names
    assert "derivative_numeric_sample" in names


def test_calculus_integral_diff_back():
    result = solve_algebra(AlgebraSolveRequest(input="integral(expr=2*x,var=x)"))
    assert result.status == "solved"
    assert result.verification.status in {"verified", "partially_verified"}
    assert any(check.name == "integral_diff_back" for check in result.verification.checks)


def test_calculus_definite_integral_newton_leibniz_check():
    result = solve_algebra(AlgebraSolveRequest(input="integral(expr=2*x,var=x,a=0,b=1)"))
    assert result.status == "solved"
    names = {check.name for check in result.verification.checks}
    assert "integral_diff_back" in names
    assert "integral_newton_leibniz" in names


def test_calculus_limit_has_recompute_check():
    result = solve_algebra(AlgebraSolveRequest(input="limit(expr=(x^2-1)/(x-1),var=x,to=1)"))
    assert result.status == "solved"
    assert any(check.name == "limit_recompute" for check in result.verification.checks)


def test_calculus_rejects_huge_derivative_order():
    result = solve_algebra(AlgebraSolveRequest(input="derivative(expr=x^2,var=x,order=99)"))
    assert result.status == "unsupported"


def test_interval_bound_parser_allows_safe_constants():
    from app.services.algebra.parser import parse_interval_bound
    import sympy as sp
    assert parse_interval_bound("0") == 0
    assert parse_interval_bound("2*pi") == 2 * sp.pi
    assert parse_interval_bound("-pi") == -sp.pi
    assert parse_interval_bound("-e") == -sp.E
    assert parse_interval_bound("pi/2") == sp.pi / 2
    assert parse_interval_bound("oo") is sp.oo


def test_interval_bound_parser_rejects_unsafe_or_variable_bounds():
    from app.services.algebra.parser import AlgebraParseError, parse_interval_bound
    with pytest.raises(AlgebraParseError):
        parse_interval_bound("sin(x)")
    with pytest.raises(AlgebraParseError):
        parse_interval_bound("1" * 30)
    with pytest.raises(AlgebraParseError):
        parse_interval_bound("__import__('os')")


def test_invalid_interval_request_uses_safe_parser_not_sympify_bomb():
    from app.schemas.algebra import AlgebraInterval
    result = solve_algebra(AlgebraSolveRequest(
        input="x-1=0",
        interval=AlgebraInterval(start="sin(x)", end="2"),
    ))
    assert any("không hợp lệ" in w.lower() or "bỏ qua" in w.lower() for w in result.warnings)


def test_mixed_eq_ineq_classified_unsupported():
    from app.services.algebra.classifier import classify_algebra_problem
    from app.services.algebra.parser import parse_algebra_problem
    problem = parse_algebra_problem("x+y=1; x>0")
    assert classify_algebra_problem(problem) == "unsupported"


def test_load_gate_capacity_and_orphan_holds_slot():
    import asyncio
    from app.services.algebra.load_gate import AlgebraLoadGate

    gate = AlgebraLoadGate()

    async def run():
        slot1 = await gate.try_acquire(1)
        assert slot1 is not None
        assert await gate.try_acquire(1) is None
        # Worker started then HTTP released (timeout path): slot still held until leave_worker.
        gate.enter_worker(slot1)
        slot1.release_http()
        assert await gate.try_acquire(1) is None
        gate.leave_worker(slot1)
        slot2 = await gate.try_acquire(1)
        assert slot2 is not None
        slot2.release_http()

    asyncio.run(run())


def test_load_gate_holds_slot_across_sequential_workers_until_http_release():
    """Rule-based then post-AI re-solve must not free capacity mid-request."""
    import asyncio
    from app.services.algebra.load_gate import AlgebraLoadGate

    gate = AlgebraLoadGate()

    async def run():
        slot = await gate.try_acquire(1)
        assert slot is not None
        gate.enter_worker(slot)
        gate.leave_worker(slot)
        # First worker finished but HTTP still open → capacity remains reserved.
        assert await gate.try_acquire(1) is None
        gate.enter_worker(slot)
        gate.leave_worker(slot)
        assert await gate.try_acquire(1) is None
        slot.release_http()
        slot2 = await gate.try_acquire(1)
        assert slot2 is not None
        slot2.release_http()

    asyncio.run(run())
