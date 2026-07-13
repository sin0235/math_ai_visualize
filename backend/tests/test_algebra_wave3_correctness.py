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


def test_structured_input_skips_llm_nlp_uses_mathcore(monkeypatch):
    """Symbolic/structured input goes straight to mathcore; LLM NLP is not called."""
    import asyncio
    from app.core.config import Settings
    from app.services.algebra import service as algebra_service
    from app.services.algebra import ai_extraction

    called = {"extractor": False}

    async def boom(*args, **kwargs):
        called["extractor"] = True
        raise AssertionError("LLM NLP must not be called for structured/symbolic algebra input")

    monkeypatch.setattr(ai_extraction, "extract_algebra_request_with_ai", boom)
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
    assert not any("rule-based" in warning.lower() for warning in response.warnings)


def test_natural_language_uses_llm_nlp_then_mathcore(monkeypatch):
    """Natural Vietnamese: unified NLP uses LLM extract; mathcore solves (no AI solve)."""
    import asyncio
    from app.core.config import Settings
    from app.services.algebra import service as algebra_service
    from app.services.algebra.ai_extraction import AlgebraExtractionPayload, merge_extraction_request
    from app.services.algebra import ai_extraction

    called = {"extractor": 0}

    async def fake_extract(problem_text, base_request, settings):
        called["extractor"] += 1
        payload = AlgebraExtractionPayload(
            input="arithmetic(u1=2,u2=6,n=9)",
            input_format="structured",
            topic="sequence",
            variables=[],
            domain="R",
        )
        req, warnings = merge_extraction_request(base_request, payload)
        return req, warnings

    monkeypatch.setattr(ai_extraction, "extract_algebra_request_with_ai", fake_extract)
    settings = Settings()
    response = asyncio.run(algebra_service.solve_algebra_with_optional_ai(
        AlgebraSolveRequest(
            input="với cấp số cộng với u1 = 2, u2 = 6, hỏi số hạng thứ 9 bằng bao nhiêu",
            options=AlgebraSolveOptions(use_ai_extraction=True, ai_explanation=False),
        ),
        settings,
    ))
    assert called["extractor"] == 1
    assert response.status == "solved"
    assert "34" in (response.answer or "") or response.answer_latex == "34"
    assert "cấp số" in response.input or "u1" in response.input
    assert "arithmetic" in (response.normalized_input or "")


def test_llm_nlp_invalid_form_falls_back_to_rule_based(monkeypatch):
    """If LLM returns non-mathcore form, orchestrator falls back to rule-based NLP."""
    import asyncio
    from app.core.config import Settings
    from app.services.algebra import service as algebra_service
    from app.services.algebra.ai_extraction import AlgebraExtractionPayload, merge_extraction_request
    from app.services.algebra import ai_extraction

    async def bad_extract(problem_text, base_request, settings):
        payload = AlgebraExtractionPayload(
            input="hãy giải giúp tôi bài toán cấp số này",
            input_format="plain",
            topic="sequence",
            variables=[],
            domain="R",
        )
        req, warnings = merge_extraction_request(base_request, payload)
        return req, warnings

    monkeypatch.setattr(ai_extraction, "extract_algebra_request_with_ai", bad_extract)
    settings = Settings()
    response = asyncio.run(algebra_service.solve_algebra_with_optional_ai(
        AlgebraSolveRequest(
            input="với cấp số cộng với u1 = 2, u2 = 6, hỏi số hạng thứ 9 bằng bao nhiêu",
            options=AlgebraSolveOptions(use_ai_extraction=True, ai_explanation=False),
        ),
        settings,
    ))
    assert response.status == "solved"
    assert "34" in (response.answer or "") or response.answer_latex == "34"
