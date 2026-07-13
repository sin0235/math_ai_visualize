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


def test_solve_request_rejects_coerced_boolean():
    with pytest.raises(ValueError):
        AlgebraSolveRequest(input="x=1", save_history=0)


def test_calculus_derivative_has_independent_checks():
    result = solve_algebra(AlgebraSolveRequest(input="derivative(expr=x^2,var=x)"))
    assert result.status == "solved"
    assert result.verification.status == "partially_verified"
    names = {check.name for check in result.verification.checks}
    assert "derivative_recompute" in names
    assert "derivative_numeric_sample" in names
    assert result.verification.method == ["solver_consistency_replay", "finite_difference"]


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
    assert result.verification.status == "partially_verified"
    assert any(check.name == "limit_recompute" for check in result.verification.checks)
    assert result.verification.method == ["solver_consistency_replay", "numeric_approach"]


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


def test_process_isolation_solves_simple_equation():
    from app.schemas.algebra import AlgebraSolveRequest
    from app.services.algebra.process_worker import solve_algebra_in_process

    result = solve_algebra_in_process(AlgebraSolveRequest(input="x**2-5*x+6=0"), timeout=15)
    assert result.status == "solved"
    assert {value.text for value in result.solution_set.values} == {"2", "3"}
    assert "interpret_ms" in result.timings_ms
    assert "parse_ms" in result.timings_ms
    assert "solve_ms" in result.timings_ms


def test_stage_timings_present_on_inprocess_solve():
    from app.schemas.algebra import AlgebraSolveRequest
    from app.services.algebra import solve_algebra

    result = solve_algebra(AlgebraSolveRequest(input="x-1=0"))
    assert result.timings_ms.get("total_ms", 0) >= 0
    assert "interpret_ms" in result.timings_ms
    assert "parse_ms" in result.timings_ms
    assert "solve_ms" in result.timings_ms


def test_empty_set_sample_corroboration_checks():
    from app.schemas.algebra import AlgebraSolveRequest
    from app.services.algebra import solve_algebra

    result = solve_algebra(AlgebraSolveRequest(input="1/(x-1)=0"))
    assert result.solution_set.kind == "empty"
    assert result.verification.status == "partially_verified"
    names = {check.name for check in result.verification.checks}
    assert "empty_solution_set" in names
    assert "empty_set_sample_corroboration" in names
    assert any("mẫu" in w.lower() or "vo nghiệm" in w.lower() or "vô nghiệm" in w.lower() for w in result.warnings)


def test_tokenizer_rejects_attribute_access_in_expr():
    from app.services.algebra.parser import AlgebraParseError, parse_algebra_problem
    import pytest

    with pytest.raises(AlgebraParseError):
        parse_algebra_problem("x.__class__")


def test_empty_after_interval_does_not_false_fail_verification():
    """Roots outside the user interval correctly yield empty without counterexample fail."""
    from app.schemas.algebra import AlgebraInterval, AlgebraSolveRequest
    from app.services.algebra import solve_algebra

    result = solve_algebra(AlgebraSolveRequest(
        input="x-1=0",
        interval=AlgebraInterval(start="2", end="3", closed_start=True, closed_end=True),
    ))
    assert result.solution_set.kind == "empty"
    assert result.verification.status != "failed"
    assert not any(c.name == "empty_set_counterexample" for c in result.verification.checks)
    assert result.status != "error"


def test_verify_false_repairs_status_after_failed_verification():
    from app.schemas.algebra import AlgebraSolveOptions, AlgebraSolveRequest
    from app.services.algebra import solve_algebra

    # Even if substitution verify would fail for a pathological case, verify=false
    # must not leave verification-driven error status.
    result = solve_algebra(AlgebraSolveRequest(
        input="x-1=0",
        options=AlgebraSolveOptions(verify=False),
    ))
    assert result.verification.status == "skipped"
    assert result.status in {"solved", "partial"}
    assert not any("kiểm chứng" in e.lower() for e in result.errors)


def test_structured_calculus_rejects_unsafe_expr():
    from app.schemas.algebra import AlgebraSolveRequest
    from app.services.algebra import solve_algebra

    result = solve_algebra(AlgebraSolveRequest(
        input="derivative(expr=x.__class__,var=x)",
        topic="calculus_derivative",
    ))
    assert result.status == "unsupported"
    assert result.errors


def test_structured_coefficient_rejects_unsafe_expr():
    from app.schemas.algebra import AlgebraSolveRequest
    from app.services.algebra import solve_algebra

    result = solve_algebra(AlgebraSolveRequest(
        input="coefficient((x).__class__,x,1)",
        topic="combinatorics_probability",
    ))
    assert result.status == "unsupported"


def test_trig_angle_unit_degree_solves_sin():
    from app.schemas.algebra import AlgebraInterval, AlgebraSolveRequest
    from app.services.algebra import solve_algebra

    result = solve_algebra(AlgebraSolveRequest(
        input="sin(x)=1/2",
        topic="trigonometry",
        angle_unit="degree",
        interval=AlgebraInterval(start="0", end="360", closed_start=True, closed_end=False),
    ))
    assert result.status in {"solved", "partial"}
    assert any("độ" in w.lower() or "degree" in w.lower() for w in result.warnings + result.assumptions)
    texts = {value.text for value in result.solution_set.values}
    # Expect 30° and 150° among solutions in [0, 360)
    assert any("30" in t for t in texts) or "30" in result.answer
    assert any("150" in t for t in texts) or "150" in result.answer
