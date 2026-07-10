import asyncio
import time

import pytest
import sympy as sp
from fastapi import HTTPException

from app.api import routes_function_analysis
from app.api.routes_function_analysis import _apply_analyzer_output_limits, _run_analyzer_job, _run_analyzer_job_sync
from app.services import function_analyzer, function_roots
from app.services.function_analyzer import analyze_function
from app.services.function_domain import FunctionDomain
from app.services.function_graph_builder import build_function_graph
from app.services.function_roots import analyze_real_roots


def test_analyzer_api_worker_returns_clean_payload():
    result = _run_analyzer_job_sync("x^2 - 1", None, None, None, None, None)

    assert "error" not in result
    assert "_parsed_expr" not in result
    assert "_evaluated_expr" not in result
    assert "_domain_set" not in result
    assert "_domain_info" not in result
    assert result["graph_points"]
    assert result["method_used"]["monotonicity"] == "symbolic_exact"
    assert result["complexity_score"] > 0


def test_analyzer_stage_timeout_returns_partial_response(monkeypatch):
    def slow_domain(*args, **kwargs):
        time.sleep(1)

    monkeypatch.setattr(function_analyzer, "continuous_domain", slow_domain)
    monkeypatch.setitem(function_analyzer._STAGE_TIMEOUT_SECONDS, "domain", 0.01)

    result = analyze_function("x^2 - 1")

    assert "error" not in result
    assert result["domain"] is None
    assert result["stage_statuses"]["domain"]["status"] == "timeout"
    assert result["derivative"] is not None


def test_analyzer_core_timeout_marks_graph_skip(monkeypatch):
    def slow_diff(*args, **kwargs):
        time.sleep(1)

    monkeypatch.setattr(function_analyzer, "diff", slow_diff)
    monkeypatch.setitem(function_analyzer._STAGE_TIMEOUT_SECONDS, "derivative", 0.01)

    result = analyze_function("x^2 - 1")

    assert "error" not in result
    assert result["stage_statuses"]["derivative"]["status"] == "timeout"
    assert result["_skip_graph"] is True


def test_analyzer_concurrency_limit_returns_429():
    acquired_slots = []
    for _ in range(routes_function_analysis.ANALYZER_CONCURRENCY_LIMIT):
        acquired = routes_function_analysis._ANALYZER_SEMAPHORE.acquire(blocking=False)
        assert acquired
        acquired_slots.append(acquired)
    try:
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(_run_analyzer_job("x^2 - 1"))
    finally:
        for _ in acquired_slots:
            routes_function_analysis._ANALYZER_SEMAPHORE.release()

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers["Retry-After"] == str(routes_function_analysis.ANALYZER_OVERLOAD_RETRY_SECONDS)


def test_analyzer_output_limit_returns_error_code():
    result = _apply_analyzer_output_limits({"geogebra_commands": ["A=(0,0)"] * 301})

    assert result["error_code"] == "ANALYZER_OUTPUT_LIMIT"


def test_analyzer_rejects_unsafe_parser_constructs():
    cases = [
        "Matrix([[1]])",
        "lambda x: x",
        "'x'",
        "x.__class__",
        "__import__('os')",
    ]

    for expression in cases:
        result = analyze_function(expression)
        assert result["error_code"] == "ANALYZER_PARSE_FAILED", expression


def test_analyzer_returns_complexity_code_for_large_exponent():
    result = analyze_function("x^100")

    assert result["error_code"] == "ANALYZER_COMPLEXITY_LIMIT"


def test_graph_builder_uses_preparsed_expression_for_samples():
    result = analyze_function("x^2 - 1")

    assert "error" not in result
    _, _, graph_points = build_function_graph(result)
    assert graph_points
    assert any(point["x"] == 0 and point["y"] == -1 for point in graph_points)


def test_analyze_function_accepts_latex_fraction():
    result = analyze_function(r"\frac{x^2 - 2*x - 4}{x + 1}")

    assert "error" not in result
    assert result["domain"] is not None
    assert result["derivative"] is not None


def test_analyze_function_accepts_nested_latex_fraction():
    result = analyze_function(r"\frac{\frac{x}{2} - 1}{x + 1}")

    assert "error" not in result
    assert result["domain"] is not None


def test_analyze_function_accepts_common_latex_syntax():
    cases = [
        r"$\frac{x^{2}-2x-4}{x+1}$",
        r"\sqrt{x^2 + 1}",
        r"2\sin{x} + \pi",
        r"\log_{2}{x}",
        r"(x+1)(x-1)",
    ]

    for expression in cases:
        result = analyze_function(expression)
        assert "error" not in result, expression
        assert result["domain"] is not None


def test_analyze_function_accepts_broader_latex_and_ocr_syntax():
    cases = [
        r"\sqrt[3]{x^2+1}",
        r"{x^2 + 1 \over x - 1}",
        r"\operatorname{ln}{x} + \mathrm{sin}{x}",
        r"\left|x-1\right| + 2x",
        r"\lvert x+1 \rvert",
        r"x^{\frac{1}{2}} + \mathrm{e}^{x}",
        "x² + 2x + 1",
        "x−1",
    ]

    for expression in cases:
        result = analyze_function(expression)
        assert "error" not in result, expression
        assert result["domain"] is not None


def test_analyze_function_reports_rational_domain_and_vertical_asymptote():
    result = analyze_function("1/(x-1)")

    assert "error" not in result
    assert "1" in result["domain"]
    assert result["vertical_asymptotes"] == [{"x": "1", "lim_right": "+∞", "lim_left": "-∞"}]


def test_analyze_function_finds_polynomial_extrema_and_intervals():
    result = analyze_function("x^3 - 3*x")

    assert "error" not in result
    critical_points = {(point["x_exact"], point["kind"]) for point in result["critical_points"]}
    assert ("-1", "max") in critical_points
    assert ("1", "min") in critical_points
    assert result["intervals_increasing"]
    assert result["intervals_decreasing"]


def test_analyze_line_position_uses_exact_roots_before_numeric_fallback():
    result = analyze_function("x^4 - 2", line={"k": 0, "b": 0})

    assert "error" not in result
    intersections = result["line_analysis"]["intersections"]
    assert {item["x_exact"] for item in intersections} == {"-2**(1/4)", "2**(1/4)"}
    assert result["line_analysis"]["intersection_count"] == 2


def test_absolute_transform_uses_geogebra_safe_abs_command():
    result = analyze_function("x^3 - 3*x + 2", transform={"type": "absolute_all", "value": 1})

    assert "error" not in result
    _, commands, _ = build_function_graph(result)
    transform_commands = [command for command in commands if command.startswith("h(x)=")]
    assert transform_commands
    assert "Abs(" not in transform_commands[0]
    assert "abs(" in transform_commands[0]


def test_analyzer_keeps_domain_hole_out_of_intersections_and_graph():
    result = analyze_function("(x^2 - 1)/(x - 1)", line={"k": 0, "b": 2})

    assert "error" not in result
    assert result["removable_holes"] == [{"x": "1", "x_exact": "1", "y": "2", "y_exact": "2", "label": "điểm khuyết"}]
    assert result["line_analysis"]["intersections"] == []
    assert result["intervals_increasing"] == ["(-∞; 1)", "(1; +∞)"]

    scene, commands, _ = build_function_graph(result)
    assert all(command != "f(x) = x+1" for command in commands)
    assert any(command.startswith("f1 = Function(") for command in commands)
    assert any(command.startswith("f2 = Function(") for command in commands)
    assert any(command.startswith("H1 = (1.0, 2.0)") for command in commands)
    hole_objects = [obj for obj in scene.model_dump(mode="json")["objects"] if obj.get("name") == "H1"]
    assert hole_objects and hole_objects[0]["metadata"]["kind"] == "removable_hole"


def test_symbolic_sign_branch_records_exact_method():
    result = analyze_function("x^3 - 3*x")

    assert "error" not in result
    assert result["method_used"]["monotonicity"] == "symbolic_exact"
    assert result["intervals_increasing"] == ["(-∞; -1)", "(1; +∞)"]
    assert result["intervals_decreasing"] == ["(-1; 1)"]


def test_domain_restricts_symbolic_intervals():
    result = analyze_function("sqrt(x)")

    assert "error" not in result
    assert result["method_used"]["monotonicity"] == "symbolic_exact"
    assert result["intervals_increasing"] == ["(0; +∞)"]
    assert result["intervals_decreasing"] == []


def _variation_v2(expression: str) -> dict:
    result = analyze_function(expression)
    assert "error" not in result
    table = result["variation_table_v2"]
    assert table is not None
    return table


def test_variation_table_v2_uses_explicit_boundary_limits():
    table = _variation_v2("exp(x)")

    assert table["status"] == "complete"
    assert table["nodes"][0]["x"] == "-∞"
    assert table["nodes"][0]["right_limit"] == {"value": "0", "status": "finite"}
    assert table["nodes"][-1]["left_limit"] == {"value": "+∞", "status": "infinite"}
    assert table["segments"] == [{"left": "-∞", "right": "+∞", "direction": "increasing", "verification": "exact", "derivative_sign": "+"}]


def test_variation_table_v2_preserves_finite_infinite_boundary_limits():
    table = _variation_v2("atan(x)")

    assert table["status"] == "complete"
    assert table["nodes"][0]["right_limit"] == {"value": "-pi/2", "status": "finite"}
    assert table["nodes"][-1]["left_limit"] == {"value": "pi/2", "status": "finite"}
    assert table["segments"][0]["direction"] == "increasing"


def test_variation_table_v2_splits_domain_at_vertical_asymptote():
    table = _variation_v2("1/x")

    assert [node["kind"] for node in table["nodes"]] == ["boundary", "asymptote", "boundary"]
    asymptote = table["nodes"][1]
    assert asymptote["x_exact"] == "0"
    assert asymptote["left_limit"] == {"value": "-∞", "status": "infinite"}
    assert asymptote["right_limit"] == {"value": "+∞", "status": "infinite"}
    assert [(segment["left"], segment["right"], segment["direction"]) for segment in table["segments"]] == [
        ("-∞", "0", "decreasing"),
        ("0", "+∞", "decreasing"),
    ]


def test_variation_table_v2_preserves_two_sided_infinite_asymptote():
    table = _variation_v2("1/(x-1)^2")

    asymptote = table["nodes"][1]
    assert asymptote["kind"] == "asymptote"
    assert asymptote["x_exact"] == "1"
    assert asymptote["left_limit"] == {"value": "+∞", "status": "infinite"}
    assert asymptote["right_limit"] == {"value": "+∞", "status": "infinite"}
    assert [segment["direction"] for segment in table["segments"]] == ["increasing", "decreasing"]


def test_variation_table_v2_starts_at_domain_boundary_for_log():
    table = _variation_v2("log(x)")

    assert [node["x"] for node in table["nodes"]] == ["0", "+∞"]
    assert table["nodes"][0]["right_limit"] == {"value": "-∞", "status": "infinite"}
    assert table["nodes"][-1]["left_limit"] == {"value": "+∞", "status": "infinite"}


def test_variation_table_v2_renders_periodic_domain_by_cycle():
    result = analyze_function("tan(x)")
    table = result["variation_table_v2"]

    assert result["periodicity"]["period"] == "pi"
    assert table["status"] == "complete"
    assert table["warnings"] == ["Bảng biến thiên biểu diễn theo một chu kỳ, với k ∈ Z."]
    assert table["segments"] == [{"left": "-pi/2 + k*pi", "right": "pi/2 + k*pi", "direction": "increasing", "verification": "periodic_exact", "derivative_sign": "+"}]


def test_variation_table_v2_keeps_removable_hole_as_hole_node():
    table = _variation_v2("(x^2 - 1)/(x - 1)")

    hole = table["nodes"][1]
    assert hole["kind"] == "hole"
    assert hole["x_exact"] == "1"
    assert hole["y_exact"] == "2"
    assert [segment["direction"] for segment in table["segments"]] == ["increasing", "increasing"]


def test_variation_table_v2_can_mark_unknown_direction(monkeypatch):
    monkeypatch.setattr(function_analyzer, "_segment_probe", lambda *_args: None)
    table = _variation_v2("exp(x)")

    assert table["status"] == "partial"
    assert table["segments"][0]["direction"] == "unknown"
    assert table["segments"][0]["verification"] == "unknown"
    assert table["segments"][0]["derivative_sign"] == "unknown"


def test_monotonicity_v2_records_periodic_general_intervals():
    result = analyze_function("sin(x)")

    assert result["periodicity"]["period"] == "2*pi"
    assert result["monotonicity_v2"]["method"] == "periodic_exact"
    assert result["monotonicity_v2"]["segments"][0]["left_exact"] == "-pi/2 + 2*k*pi"
    assert result["monotonicity_v2"]["segments"][0]["parameter_domain"] == "Z"


def test_concavity_v2_handles_constant_second_derivative():
    result = analyze_function("x^2")

    assert result["concavity_v2"]["method"] == "symbolic_exact"
    assert result["concavity_v2"]["segments"] == [{"left": "-∞", "right": "+∞", "left_exact": "-oo", "right_exact": "oo", "sign": "+", "verification": "exact", "kind": "convex", "second_derivative_sign": "+"}]
    assert result["concave_up_intervals"] == ["(-∞; +∞)"]


def test_log_concavity_and_vertical_asymptote_from_domain_boundary():
    result = analyze_function("log(x)")

    assert result["concavity_v2"]["segments"][0]["kind"] == "concave"
    vertical = result["asymptotes_v2"]["vertical"][0]
    assert vertical["x_exact"] == "0"
    assert "domain_boundary" in vertical["source"]
    assert vertical["right_limit"]["status"] == "infinite"


def test_stationary_inflection_is_not_local_extremum():
    result = analyze_function("x^3")

    assert result["critical_points_v2"][0]["kind"] == "stationary_inflection"
    assert result["critical_points_v2"][0]["evidence"] == "second_derivative_sign_change"
    assert result["inflection_points_v2"][0]["x_exact"] == "0"


def test_periodic_tan_cot_asymptote_families():
    tan_result = analyze_function("tan(x)")
    cot_result = analyze_function("cot(x)")

    assert tan_result["asymptotes_v2"]["periodic_vertical_families"][0]["x_exact"] == "pi/2 + k*pi"
    assert cot_result["asymptotes_v2"]["periodic_vertical_families"][0]["x_exact"] == "k*pi"


def test_asymptote_v2_preserves_exact_values_and_two_oblique_directions():
    rational = analyze_function("1/(x-sqrt(2))")
    oblique = analyze_function("sqrt(x^2 + 1)")

    assert rational["asymptotes_v2"]["vertical"][0]["x_exact"] == "sqrt(2)"
    assert rational["asymptotes_v2"]["vertical"][0]["approx"] == "1.4142"
    directions = {item["direction"] for item in oblique["asymptotes_v2"]["oblique"]}
    assert directions == {"+∞", "-∞"}


def test_x_intercepts_exclude_complex_roots_and_report_complete_empty_set():
    result = analyze_function("x^2 + 1")

    assert result["x_intercepts"] == []
    assert result["x_intercepts_v2"]["status"] == "complete"
    assert result["x_intercepts_v2"]["total_known"] == 0
    assert result["x_intercepts_v2"]["families"] == []


def test_x_intercepts_filter_domain_before_counting_roots():
    result = analyze_function("(x^2 - 1)/(x - 1)")

    assert result["x_intercepts"] == ["-1"]
    assert result["x_intercepts_v2"]["total_known"] == 1
    assert result["x_intercepts_v2"]["roots"][0]["residual"] == 0


def test_x_intercepts_do_not_silently_truncate_after_six_roots():
    variable = sp.Symbol("t", real=True)
    expression = sp.prod(variable - root for root in range(-3, 4))
    roots = analyze_real_roots(expression, variable, FunctionDomain.from_set(sp.S.Reals))
    limited = analyze_real_roots(expression, variable, FunctionDomain.from_set(sp.S.Reals), max_points=3)

    assert roots.status == "complete"
    assert roots.total_known == 7
    assert roots.truncated is False
    assert len(roots.roots) == 7
    assert limited.status == "partial"
    assert limited.total_known == 7
    assert limited.truncated is True
    assert len(limited.roots) == 3


def test_periodic_x_intercepts_use_exact_family():
    result = analyze_function("sin(x)")

    roots = result["x_intercepts_v2"]
    assert roots["status"] == "complete"
    assert roots["total_known"] is None
    assert roots["roots"] == []
    assert roots["families"]
    assert roots["families"][0]["parameter_domain"] == "Z"


def test_numeric_root_fallback_is_partial_and_residual_verified(monkeypatch):
    variable = sp.Symbol("t", real=True)
    original_solveset = function_roots.sp.solveset
    target = sp.sin(variable) - variable / 2

    def unresolved(expr, symbol, domain):
        if expr == target:
            return sp.ConditionSet(symbol, sp.Eq(expr, 0), domain)
        return original_solveset(expr, symbol, domain=domain)

    monkeypatch.setattr(function_roots.sp, "solveset", unresolved)
    result = analyze_real_roots(target, variable, FunctionDomain.from_set(sp.S.Reals))

    assert result.status == "partial"
    assert result.method == "numeric_adaptive"
    assert result.search_window == (-20.0, 20.0)
    assert result.roots
    assert all(root.residual <= 1e-8 for root in result.roots)
    assert all(root.error_bound is not None for root in result.roots)


def test_interval_constant_on_open_interval_attains_both_extrema():
    interval = analyze_function("1", interval={"a": 0, "b": 1, "open_a": True, "open_b": True})["interval_analysis"]

    assert interval["supremum"]["status"] == "maximum"
    assert interval["infimum"]["status"] == "minimum"
    assert interval["supremum"]["attainment_set_exact"] == "Interval.open(0, 1)"
    assert interval["infimum"]["attainment_set_exact"] == "Interval.open(0, 1)"


def test_interval_tie_uses_all_attainment_points():
    interval = analyze_function("x^2*(1-x)^2", interval={"a": 0, "b": 1})["interval_analysis"]

    assert interval["infimum"]["status"] == "minimum"
    assert interval["infimum"]["attainment_set_exact"] == "{0, 1}"
    assert {point["x_exact"] for point in interval["infimum"]["points"]} == {"0", "1"}


def test_interval_splits_domain_and_reports_unbounded_sides():
    interval = analyze_function("1/(x-1)", interval={"a": 0, "b": 2})["interval_analysis"]

    assert len(interval["domain_components"]) == 2
    assert interval["supremum"]["status"] == "unbounded_above"
    assert interval["infimum"]["status"] == "unbounded_below"
    singular_limits = [item for item in interval["boundary_evidence"] if item["x_exact"] == "1"]
    assert {item["value"]["value_exact"] for item in singular_limits} == {"oo", "-oo"}


def test_line_intersections_include_residual_and_complete_count():
    line = analyze_function("x^4 - 2", line={"k": 0, "b": 0})["line_analysis"]

    assert line["intersection_count"] == 2
    assert line["intersection_count_status"] == "complete"
    assert line["roots_v2"]["status"] == "complete"
    assert all(point["residual"] == 0 for point in line["intersections"])
    assert all(point["verification"] == "symbolic_exact" for point in line["intersections"])


def test_area_is_split_between_consecutive_intersections():
    area = analyze_function("x^3-x", line={"k": 0, "b": 0})["line_analysis"]["area_v2"]

    assert area["status"] == "complete"
    assert area["total_exact"] == "1/2"
    assert [component["area_exact"] for component in area["components"]] == ["1/4", "1/4"]


def test_area_rejects_component_crossing_singularity():
    line = analyze_function("1/x", line={"k": 1, "b": 0})["line_analysis"]

    assert line["intersection_count"] == 2
    assert line["area_between_curves"] is None
    assert line["area_v2"]["status"] == "partial"
    assert line["area_v2"]["warnings"]


def test_tangent_rejects_cusp_or_corner():
    tangent = analyze_function("Abs(x)", line={"mode": "tangent_at", "x0": 0})["line_analysis"]

    assert tangent["status"] == "nondifferentiable"
    assert tangent["equation_exact"] is None
    assert tangent["left_slope"]["value_exact"] == "-1"
    assert tangent["right_slope"]["value_exact"] == "1"


def test_tangent_supports_one_sided_vertical_domain_endpoint():
    tangent = analyze_function("sqrt(x)", line={"mode": "tangent_at", "x0": 0})["line_analysis"]

    assert tangent["status"] == "vertical_tangent"
    assert tangent["equation_exact"] == "x = 0"
    assert tangent["left_slope"]["status"] == "unavailable"
    assert tangent["right_slope"]["value_exact"] == "oo"


def test_regular_tangent_keeps_exact_slope_and_contact_verification():
    tangent = analyze_function("x^2", line={"mode": "tangent_at", "x0": 1})["line_analysis"]

    assert tangent["status"] == "regular_tangent"
    assert tangent["k_exact"] == "2"
    assert tangent["equation_exact"] == "y = 2*x - 1"
    assert tangent["contact_limit"] == "0"
