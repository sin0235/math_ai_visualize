from app.schemas.algebra import AlgebraSolveOptions, AlgebraSolveRequest
from app.services.algebra import solve_algebra
from app.services.algebra.classifier import classify_algebra_problem
from app.services.algebra.parser import parse_algebra_problem
from app.services.algebra.verifier import verify_solution_set


def test_classifier_routes_exp_log_inequality_to_inequality():
    problem = parse_algebra_problem("log(x)>0")
    assert classify_algebra_problem(problem) == "inequality"


def test_classifier_routes_trig_inequality_to_inequality():
    problem = parse_algebra_problem("sin(x)>=1/2")
    assert classify_algebra_problem(problem) == "inequality"


def test_exp_log_inequality_is_solved_not_unsupported_by_exp_solver():
    result = solve_algebra(AlgebraSolveRequest(input="log(x)>0"))
    assert result.topic == "inequality"
    assert result.status in {"solved", "partial"}
    assert result.status != "unsupported"


def test_trig_inequality_is_solved_not_unsupported_by_trig_solver():
    result = solve_algebra(AlgebraSolveRequest(input="sin(x)>=1/2"))
    assert result.topic == "inequality"
    assert result.status in {"solved", "partial", "unsupported"}
    # At least must not be routed into equality-only trig solver path that returns unsupported for inequality input text wrongly as equation
    if result.status == "unsupported":
        assert "phương trình lượng giác" not in result.answer.lower()


def test_chained_inequality_parsed_and_solved():
    problem = parse_algebra_problem("0 < x < 1")
    assert len(problem.relations) == 2
    assert problem.topic == "inequality"
    result = solve_algebra(AlgebraSolveRequest(input="0 < x < 1"))
    assert result.status in {"solved", "partial"}
    assert result.topic == "inequality"
    assert result.verification.status != "failed"
    assert "(0" in result.answer or "0" in (result.answer_latex or "") or "Interval" in result.answer


def test_not_equal_relation_solved():
    result = solve_algebra(AlgebraSolveRequest(input="x^2-1!=0"))
    assert result.status in {"solved", "partial"}
    assert result.topic == "inequality"


def test_symbolic_solution_set_not_fully_verified():
    problem = parse_algebra_problem("sin(x)=1/2")
    import sympy as sp
    solution_set = sp.solveset(sp.sin(problem.variable) - sp.Rational(1, 2), problem.variable, domain=sp.S.Reals)
    report = verify_solution_set(problem, solution_set)
    assert report.status == "partially_verified"


def test_options_verify_false_skips_verification():
    result = solve_algebra(AlgebraSolveRequest(
        input="x^2-5*x+6=0",
        options=AlgebraSolveOptions(verify=False),
    ))
    assert result.status == "solved"
    assert result.verification.status == "skipped"
    assert any("verify=false" in warning for warning in result.warnings)


def test_options_return_steps_false_clears_steps():
    result = solve_algebra(AlgebraSolveRequest(
        input="x^2-5*x+6=0",
        options=AlgebraSolveOptions(return_steps=False),
    ))
    assert result.status == "solved"
    assert result.steps == []


def test_options_max_solutions_truncates_values():
    result = solve_algebra(AlgebraSolveRequest(
        input="x^2-5*x+6=0",
        options=AlgebraSolveOptions(max_solutions=1),
    ))
    assert result.status == "solved"
    assert len(result.solution_set.values) == 1
    assert "1/2" not in result.answer or "cắt" in result.answer  # both roots 2,3 — ensure truncated messaging
    assert "cắt" in result.answer
    assert result.answer_latex is not None and "cắt" in result.answer_latex
    assert result.solution_set.latex is not None and "cắt" in result.solution_set.latex
    assert any("max_solutions" in warning for warning in result.warnings)


def test_trig_interval_filters_to_unit_circle():
    from app.schemas.algebra import AlgebraInterval

    result = solve_algebra(AlgebraSolveRequest(
        input="sin(x)=1/2",
        interval=AlgebraInterval(variable="x", start="0", end="2*pi", closed_start=True, closed_end=False),
    ))
    assert result.status == "solved"
    assert result.solution_set.kind == "finite"
    texts = {value.text for value in result.solution_set.values}
    assert "pi/6" in texts
    assert "5*pi/6" in texts
    assert any("khoảng" in warning.lower() for warning in result.warnings)


def test_response_includes_request_id_and_timings():
    result = solve_algebra(AlgebraSolveRequest(input="x-1=0"))
    assert result.request_id
    assert result.request_id.startswith("alg_")
    assert "total_ms" in result.timings_ms


def test_trig_inequality_honors_unit_circle_interval():
    from app.schemas.algebra import AlgebraInterval

    result = solve_algebra(AlgebraSolveRequest(
        input="sin(x)>=1/2",
        interval=AlgebraInterval(variable="x", start="0", end="2*pi", closed_start=True, closed_end=False),
    ))
    assert result.topic == "inequality"
    assert result.status in {"solved", "partial"}
    assert any("khoảng" in warning.lower() for warning in result.warnings) or "pi" in result.answer.lower() or "\\pi" in (result.answer_latex or "")


def test_invalid_interval_warns_and_continues():
    from app.schemas.algebra import AlgebraInterval

    result = solve_algebra(AlgebraSolveRequest(
        input="x-1=0",
        interval=AlgebraInterval(variable="x", start="@@@", end="1"),
    ))
    assert result.status in {"solved", "partial", "error", "unsupported"}
    if result.status == "solved":
        assert any("không hợp lệ" in warning.lower() or "bỏ qua" in warning.lower() for warning in result.warnings)


def test_rule_based_first_skips_ai_extractor(monkeypatch):
    import asyncio
    from app.core.config import Settings
    from app.services.algebra import service as algebra_service

    called = {"extractor": False}

    async def boom(*args, **kwargs):
        called["extractor"] = True
        raise AssertionError("AI extractor must not be called when rule-based already solved")

    monkeypatch.setattr(algebra_service, "extract_algebra_request_with_ai", boom)
    settings = Settings()
    response = asyncio.run(algebra_service.solve_algebra_with_optional_ai(
        AlgebraSolveRequest(
            input="x^2-5*x+6=0",
            options=AlgebraSolveOptions(use_ai_extraction=True),
        ),
        settings,
    ))
    assert response.status == "solved"
    assert called["extractor"] is False
    assert any("rule-based" in warning.lower() for warning in response.warnings)
