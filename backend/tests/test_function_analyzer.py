import asyncio
import os
import time

import pytest
import sympy as sp
from fastapi import HTTPException
from pydantic import ValidationError

from app.api import routes_function_analysis
from app.api.routes_function_analysis import _analysis_response, _apply_analyzer_output_limits, _run_analyzer_job, _run_analyzer_job_sync, analyzer_capabilities_endpoint
from app.schemas.analysis import AnalyzeRequest, AnalyzerBaseRequest, AnalyzerIntervalToolRequest, AnalyzerSessionResponse, AnalyzerToolResponse, GraphAnalysis, GraphSamplesRequest
from app.services import analyzer_runtime, function_analyzer, function_roots
from app.services.analyzer_errors import AnalyzerErrorCode, analyzer_error_from_payload
from app.services.function_analysis_capabilities import analyzer_capability_registry
from app.services.function_analysis_steps import build_analysis_steps
from app.services.function_analyzer import analyze_function
from app.services.function_analysis_verification import build_verification_report
from app.services.function_domain import FunctionDomain
from app.services.function_graph_builder import build_function_graph
from app.services.function_graph_sampling import build_graph_analysis
from app.services.function_roots import analyze_real_roots
from app.services.safe_math_parser import parse_safe_math_expression, safe_math_parser_registry


def _runtime_test_worker(result_queue, payload):
    delay = (payload.get("parameters") or {}).get("delay", payload.get("delay", 0))
    time.sleep(delay)
    result_queue.put(("ok", {"expression": payload["expression"], "worker_pid": os.getpid()}))


class _DisconnectAfter:
    def __init__(self, delay: float):
        self.deadline = time.monotonic() + delay

    async def is_disconnected(self) -> bool:
        return time.monotonic() >= self.deadline


@pytest.fixture(autouse=True)
def _clear_analyzer_runtime_state():
    analyzer_runtime.clear_runtime_state()
    yield
    analyzer_runtime.clear_runtime_state()


def test_capability_registry_uses_parser_allowlist_and_tested_examples():
    registry = analyzer_capability_registry()

    assert registry["parser"] == safe_math_parser_registry()
    assert analyzer_capabilities_endpoint().version == registry["version"]
    assert registry["parameters"]["ranges"]["m"] == {"min": -10.0, "max": 10.0, "step": 0.1}
    for example in registry["examples"]:
        parsed = parse_safe_math_expression(example["expression"])
        assert parsed.expr is not None, example["expression"]


def test_analyzer_capabilities_are_expression_specific():
    polynomial = analyze_function("x^2 - 1")
    piecewise = analyze_function("Piecewise((x^2, x<0), (x, x>=0))")
    parameterized = analyze_function("x^2 + m*x + 1", parameter_mode="symbolic")

    assert polynomial["capabilities"]["expression"]["piecewise"] is False
    assert polynomial["capabilities_v2"] == polynomial["capabilities"]
    assert polynomial["capabilities"]["tools"]["tangent"] is True
    assert piecewise["capabilities"]["expression"]["piecewise"] is True
    assert piecewise["capabilities"]["limitations"]
    assert parameterized["capabilities"]["expression"]["parameters"] == ["m"]
    assert parameterized["capabilities"]["tools"]["parameter_conditions"] is True


def test_exact_approx_contract_is_additive_for_roots_points_extrema_and_asymptotes():
    polynomial = analyze_function("x^3 - 3*x", interval={"a": -2, "b": 2})
    rational = analyze_function("1/(x-1)")

    root = polynomial["x_intercepts_v2"]["roots"][0]
    point = polynomial["critical_points"][0]
    assert root["x"] and root["value"]["exact"]
    assert point["x"] and point["x_value"]["latex"]
    assert polynomial["interval_analysis"]["supremum"]["value"]
    assert polynomial["interval_analysis"]["supremum"]["value_v2"]["method"] == "symbolic_range"
    assert rational["vertical_asymptotes"][0]["x"] == "1"
    assert rational["asymptotes_v2"]["vertical"][0]["x_value"]["exact"] == "1"


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


def test_analyzer_session_and_tool_use_serialized_evidence(monkeypatch):
    data = _run_analyzer_job_sync("1/(x-1)", None, None, None, None, None)
    response = _analysis_response("1/(x-1)", data).model_dump(mode="json")
    session = analyzer_runtime.create_analysis_session("user:one", response)
    quadratic_data = _run_analyzer_job_sync("x^2", None, None, None, None, None)
    quadratic_response = _analysis_response("x^2", quadratic_data).model_dump(mode="json")
    quadratic_session = analyzer_runtime.create_analysis_session("user:one", quadratic_response)

    monkeypatch.setattr(function_analyzer, "continuous_domain", lambda *_args, **_kwargs: pytest.fail("tool không được giải lại miền"))
    tool = function_analyzer.analyze_function_tool_from_evidence(
        session.result,
        "interval-extrema",
        {"a": 0, "b": 2},
    )

    assert session.analysis_id
    assert analyzer_runtime.get_analysis_session(session.analysis_id, "user:one") == session
    with pytest.raises(KeyError):
        analyzer_runtime.get_analysis_session(session.analysis_id, "user:two")
    assert tool["interval_analysis"]["status"] == "complete"
    assert len(tool["interval_analysis"]["domain_components"]) == 2

    tangent_family = function_analyzer.analyze_function_tool_from_evidence(
        quadratic_session.result,
        "line",
        {"mode": "tangent_through_point", "x0": 0, "b": -1},
    )
    assert set(tangent_family["line_analysis"]["graph_expressions"]) == {"-2*x - 1", "2*x - 1"}


def test_function_graph_builds_all_tangent_family_commands():
    analysis = analyze_function("x^2")
    analysis["line_analysis"] = {
        "mode": "tangent_through_point",
        "graph_expressions": ["-2*x - 1", "2*x - 1"],
    }

    _, commands, _ = build_function_graph(analysis)

    assert analysis["graph_analysis_v2"]["segments"][0]["left_window_clipped"] is True
    assert analysis["graph_analysis_v2"]["segments"][0]["right_window_clipped"] is True
    assert "f(x)=x^2" in {command.replace(" ", "") for command in commands}
    assert not any(command.startswith("D1") for command in commands)
    assert "g1(x)=-2*x-1" in commands
    assert "g2(x)=2*x-1" in commands


def test_function_graph_does_not_clip_piecewise_boundary():
    analysis = analyze_function("Piecewise((x^2, x<0), (x, x>=0))")

    build_function_graph(analysis)

    left_branch = next(segment for segment in analysis["graph_analysis_v2"]["segments"] if segment["end"]["exact"] == "0")
    right_branch = next(segment for segment in analysis["graph_analysis_v2"]["segments"] if segment["start"]["exact"] == "0")
    assert left_branch["right_window_clipped"] is False
    assert right_branch["left_window_clipped"] is False


def test_analyzer_session_rejects_engine_version_mismatch(monkeypatch):
    session = analyzer_runtime.create_analysis_session("user:one", {"expression": "x"})

    monkeypatch.setattr(analyzer_runtime, "ANALYZER_ENGINE_VERSION", "changed-engine")

    with pytest.raises(KeyError):
        analyzer_runtime.get_analysis_session(session.analysis_id, "user:one")


def test_analyzer_cache_is_scoped_and_reuses_completed_result(monkeypatch):
    starts = 0
    original_start = analyzer_runtime._start_job

    def counted_start(*args, **kwargs):
        nonlocal starts
        starts += 1
        return original_start(*args, **kwargs)

    monkeypatch.setattr(analyzer_runtime, "_analysis_worker", _runtime_test_worker)
    monkeypatch.setattr(analyzer_runtime, "_start_job", counted_start)

    async def scenario():
        first = await analyzer_runtime.run_cached_analysis("x", scope="user:one")
        reused = await analyzer_runtime.run_cached_analysis("x", scope="user:one")
        isolated = await analyzer_runtime.run_cached_analysis("x", scope="user:two")
        return first, reused, isolated

    first, reused, isolated = asyncio.run(scenario())

    assert starts == 2
    assert reused == first
    assert isolated["expression"] == first["expression"]


def test_analyzer_shared_job_survives_one_waiter_disconnect(monkeypatch):
    monkeypatch.setattr(analyzer_runtime, "_analysis_worker", _runtime_test_worker)

    async def scenario():
        payload = {"delay": 0.2}
        disconnected = asyncio.create_task(analyzer_runtime.run_cached_analysis(
            "x", parameters=payload, scope="shared", request=_DisconnectAfter(0.08)
        ))
        waiting = asyncio.create_task(analyzer_runtime.run_cached_analysis(
            "x", parameters=payload, scope="shared"
        ))
        with pytest.raises(asyncio.CancelledError):
            await disconnected
        result = await waiting
        return result

    result = asyncio.run(scenario())

    assert result["expression"] == "x"
    assert analyzer_runtime._ANALYZER_INFLIGHT == {}


def test_analyzer_last_waiter_disconnect_terminates_process(monkeypatch):
    jobs = []
    original_start = analyzer_runtime._start_job

    def capture_job(*args, **kwargs):
        job = original_start(*args, **kwargs)
        jobs.append(job)
        return job

    monkeypatch.setattr(analyzer_runtime, "_analysis_worker", _runtime_test_worker)
    monkeypatch.setattr(analyzer_runtime, "_start_job", capture_job)

    async def scenario():
        with pytest.raises(asyncio.CancelledError):
            await analyzer_runtime.run_cached_analysis(
                "x", parameters={"delay": 2}, scope="cancelled", request=_DisconnectAfter(0.05)
            )
        await asyncio.sleep(0.05)

    asyncio.run(scenario())

    assert analyzer_runtime._ANALYZER_INFLIGHT == {}
    assert len(jobs) == 1 and not jobs[0].process.is_alive()


def test_analyzer_timeout_cleans_process_and_inflight(monkeypatch):
    jobs = []
    original_start = analyzer_runtime._start_job

    def capture_job(*args, **kwargs):
        job = original_start(*args, **kwargs)
        jobs.append(job)
        return job

    monkeypatch.setattr(analyzer_runtime, "_analysis_worker", _runtime_test_worker)
    monkeypatch.setattr(analyzer_runtime, "_start_job", capture_job)
    monkeypatch.setattr(analyzer_runtime, "ANALYZER_TIMEOUT_SECONDS", 0.05)

    result = asyncio.run(analyzer_runtime.run_cached_analysis(
        "x", parameters={"delay": 2}, scope="timeout"
    ))

    assert result["error_code"] == AnalyzerErrorCode.TIMEOUT.value
    assert analyzer_runtime._ANALYZER_INFLIGHT == {}
    assert len(jobs) == 1 and not jobs[0].process.is_alive()


def test_analyzer_session_tool_schemas_and_openapi_are_typed():
    base_schema = AnalyzerBaseRequest.model_json_schema()
    tool_schema = AnalyzerIntervalToolRequest.model_json_schema()

    assert base_schema["additionalProperties"] is False
    assert tool_schema["additionalProperties"] is False
    assert tool_schema["properties"]["interval"]["$ref"].endswith("/AnalysisInterval")
    assert "analysis_id" in AnalyzerSessionResponse.model_fields
    assert AnalyzerToolResponse.model_fields["tool"].annotation is not str


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
    assert build_verification_report(result)["status"] == "partially_verified"
    assert build_verification_report(result)["possibly_incomplete"] is True


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


def test_analyzer_error_taxonomy_hides_internal_detail():
    error = analyzer_error_from_payload({
        "error": "provider-secret raw traceback",
        "error_code": "ANALYZE_FAILED",
        "stage_statuses": {"solver": {"status": "failed"}},
    })

    assert error.status_code == 500
    assert error.detail == {
        "code": AnalyzerErrorCode.INTERNAL_ERROR.value,
        "message": "Analyzer gặp lỗi nội bộ.",
        "correlation_id": "",
        "stage": "solver",
        "retryable": True,
    }
    assert "provider-secret" not in str(error.detail)


def test_analyzer_error_taxonomy_maps_parse_complexity_and_timeout():
    cases = [
        ("ANALYZER_PARSE_FAILED", 422, AnalyzerErrorCode.PARSE_FAILED),
        ("ANALYZER_OUTPUT_LIMIT", 413, AnalyzerErrorCode.COMPLEXITY_LIMIT),
        ("ANALYZER_TIMEOUT", 504, AnalyzerErrorCode.TIMEOUT),
    ]

    for legacy_code, expected_status, expected_code in cases:
        error = analyzer_error_from_payload({"error": "raw", "error_code": legacy_code})
        assert error.status_code == expected_status
        assert error.detail["code"] == expected_code.value


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


def test_transform_contract_uses_confirmed_horizontal_shift_convention():
    preview = analyze_function("x^2", transform={"type": "horizontal_shift", "value": 2})["transform_preview"]

    assert preview["expression"] == "(x - 2.0)**2"
    assert preview["expression_template"] == "g(x)=f(x-a)"
    assert preview["convention"] == "g(x)=f(x-a); a>0: dịch phải; a<0: dịch trái"
    assert preview["requires_value"] is True
    assert {(anchor["source_x"], anchor["target_x"]) for anchor in preview["anchors"]} == {
        (-1.0, 1.0),
        (0.0, 2.0),
        (1.0, 3.0),
    }


def test_transform_contract_handles_negative_and_zero_scales():
    vertical = analyze_function("x + 1", transform={"type": "vertical_scale", "value": -2})["transform_preview"]
    horizontal_zero = analyze_function("x^2 + 1", transform={"type": "horizontal_scale", "value": 0})["transform_preview"]
    reflection = analyze_function("x^2 + 1", transform={"type": "reflect_x"})["transform_preview"]

    assert vertical["expression"] == "-2.0*x - 2.0"
    assert all(anchor["target_y"] == pytest.approx(-2 * anchor["source_y"]) for anchor in vertical["anchors"])
    assert horizontal_zero["expression"] == "1"
    assert horizontal_zero["anchors"] == []
    assert "a=0" in horizontal_zero["convention"]
    assert reflection["requires_value"] is False


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


def test_variation_table_v2_does_not_bridge_or_probe_outside_disconnected_domain():
    table = _variation_v2("1/sqrt(x^2-1)")

    left_asymptote = next(node for node in table["nodes"] if node["x_exact"] == "-1")
    right_asymptote = next(node for node in table["nodes"] if node["x_exact"] == "1")
    assert left_asymptote["left_limit"] == {"value": "+∞", "status": "infinite"}
    assert "right_limit" not in left_asymptote
    assert "left_limit" not in right_asymptote
    assert right_asymptote["right_limit"] == {"value": "+∞", "status": "infinite"}
    assert [(segment["left"], segment["right"]) for segment in table["segments"]] == [("-∞", "-1"), ("1", "+∞")]


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
    assert interval["domain_components"][0]["end_approx"] == 1.0
    assert interval["domain_components"][1]["start_approx"] == 1.0
    assert interval["supremum"]["status"] == "unbounded_above"
    assert interval["infimum"]["status"] == "unbounded_below"
    singular_limits = [item for item in interval["boundary_evidence"] if item["x_exact"] == "1"]
    assert {item["value"]["value_exact"] for item in singular_limits} == {"oo", "-oo"}


def test_line_intersections_include_residual_and_complete_count():
    line = analyze_function("x^4 - 2", line={"k": 0, "b": 0})["line_analysis"]

    assert line["intersection_count"] == 2
    assert line["intersection_count_status"] == "complete"
    assert line["graph_expression"] == "0"
    assert line["equation_exact"] == "y = 0"
    assert line["roots_v2"]["status"] == "complete"
    assert all(point["residual"] == 0 for point in line["intersections"])
    assert all(point["verification"] == "symbolic_exact" for point in line["intersections"])


def test_line_intersection_reports_exact_tangency_and_multiplicity():
    line = analyze_function("x^2", line={"k": 0, "b": 0})["line_analysis"]

    assert line["intersection_count"] == 1
    assert line["intersections"][0]["multiplicity"] == 2
    assert line["intersections"][0]["contact_kind"] == "tangent"


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
    assert tangent["x0_exact"] == "0"
    assert "graph_expression" not in tangent
    assert tangent["left_slope"]["status"] == "unavailable"
    assert tangent["right_slope"]["value_exact"] == "oo"


def test_regular_tangent_keeps_exact_slope_and_contact_verification():
    tangent = analyze_function("x^2", line={"mode": "tangent_at", "x0": 1})["line_analysis"]

    assert tangent["status"] == "regular_tangent"
    assert tangent["k_exact"] == "2"
    assert tangent["equation_exact"] == "y = 2*x - 1"
    assert tangent["graph_expression"] == "2*x - 1"
    assert tangent["contact_limit"] == "0"


def test_normal_line_uses_verified_tangent_evidence():
    normal = analyze_function("x^2", line={"mode": "normal_at", "x0": 1})["line_analysis"]

    assert normal["status"] == "regular_normal"
    assert normal["k_exact"] == "-1/2"
    assert normal["equation_exact"] == "y = 3/2 - x/2"
    assert normal["graph_expression"] == "3/2 - x/2"
    assert normal["source_tangent_status"] == "regular_tangent"


def test_normal_line_handles_horizontal_and_vertical_tangents():
    vertical = analyze_function("x^2", line={"mode": "normal_at", "x0": 0})["line_analysis"]
    horizontal = analyze_function("sqrt(x)", line={"mode": "normal_at", "x0": 0})["line_analysis"]

    assert vertical["status"] == "vertical_normal"
    assert vertical["equation_exact"] == "x = 0"
    assert vertical["graph_expression"] is None
    assert horizontal["status"] == "regular_normal"
    assert horizontal["equation_exact"] == "y = 0"
    assert horizontal["graph_expression"] == "0"


def test_tangent_at_point_requires_exact_membership():
    valid = analyze_function("x^2", line={"mode": "tangent_at_point", "x0": 1, "y0": 1})["line_analysis"]
    invalid = analyze_function("x^2", line={"mode": "tangent_at_point", "x0": 1, "y0": 2})["line_analysis"]

    assert valid["status"] == "regular_tangent"
    assert valid["mode"] == "tangent_at_point"
    assert valid["graph_expression"] == "2*x - 1"
    assert valid["point_verification"] == "exact_point_substitution"
    assert invalid["status"] == "point_not_on_graph"
    assert invalid["actual_y_exact"] == "1"
    assert invalid["graph_expression"] is None


def test_tangent_family_supports_parallel_perpendicular_and_through_point():
    parallel = analyze_function("x^2", line={"mode": "tangent_parallel", "k": 2})["line_analysis"]
    perpendicular = analyze_function("x^2", line={"mode": "tangent_perpendicular", "k": 1})["line_analysis"]
    through_point = analyze_function("x^2", line={"mode": "tangent_through_point", "x0": 0, "b": -1})["line_analysis"]

    assert parallel["status"] == "complete"
    assert parallel["graph_expressions"] == ["2*x - 1"]
    assert perpendicular["graph_expressions"] == ["-x - 1/4"]
    assert set(through_point["graph_expressions"]) == {"-2*x - 1", "2*x - 1"}
    assert through_point["tangent_count"] == 2
    assert all(item["verification"].startswith("difference_quotient") for item in through_point["tangents"])


def test_tangent_family_does_not_claim_vertical_solution_for_horizontal_reference():
    result = analyze_function("x^(1/3)", line={"mode": "tangent_perpendicular", "k": 0})["line_analysis"]

    assert result["status"] == "unsupported"
    assert result["graph_expressions"] == []
    assert result["warnings"]


def test_graph_analysis_splits_real_domain_and_respects_point_cap():
    variable = sp.Symbol("x", real=True)
    expression = parse_safe_math_expression("1/(x-1)").expr
    domain = FunctionDomain.from_set(sp.calculus.util.continuous_domain(expression, variable, sp.S.Reals))

    graph = build_graph_analysis(
        expression,
        variable,
        domain,
        {},
        requested_interval={"a": 0, "b": 2},
        plot_window=(-3, 3),
        max_points=64,
    )

    assert graph["point_count"] <= 64
    assert len(graph["segments"]) == 2
    assert graph["segments"][0]["end"]["exact"] == "1"
    assert graph["segments"][0]["right_open"] is True
    assert graph["segments"][1]["start"]["exact"] == "1"
    assert graph["segments"][1]["left_open"] is True


def test_piecewise_parser_and_graph_preserve_branch_endpoints():
    variable = sp.Symbol("x", real=True)
    expression = parse_safe_math_expression("Piecewise((x, x < 0), (x^2, True))").expr

    graph = build_graph_analysis(
        expression,
        variable,
        FunctionDomain.from_set(sp.S.Reals),
        {},
        plot_window=(-2, 2),
        max_points=80,
    )

    assert [segment["expression_exact"] for segment in graph["segments"]] == ["x", "x**2"]
    assert graph["segments"][0]["right_endpoint"]["open"] is True
    assert graph["segments"][1]["left_endpoint"]["open"] is False
    assert graph["segments"][1]["left_endpoint"]["attained"] is True


def test_graph_builder_exposes_v2_and_uses_domain_components_for_geogebra():
    result = analyze_function("1/(x-1)", interval={"a": 0, "b": 2})

    _, commands, legacy_points = build_function_graph(result)

    assert result["graph_analysis_v2"]["segments"]
    assert len(result["graph_analysis_v2"]["segments"]) == 2
    assert len(legacy_points) == result["graph_analysis_v2"]["point_count"]
    function_commands = [command for command in commands if "Function(" in command]
    assert len(function_commands) == 2
    assert all(", 1" in command for command in function_commands)


def test_analyze_response_keeps_legacy_and_v2_contracts():
    data = _run_analyzer_job_sync("x^2 - 1", None, None, None, None, None)
    payload = _analysis_response("x^2 - 1", data).model_dump(mode="json")

    assert {"x_intercepts", "interval_analysis", "line_analysis", "graph_points"} <= payload.keys()
    assert {"x_intercepts_v2", "domain_partition_v2", "variation_table_v2", "graph_analysis_v2"} <= payload.keys()
    assert payload["x_intercepts"] == ["-1", "1"]
    assert payload["x_intercepts_v2"]["status"] == "complete"
    assert payload["graph_points"]
    assert payload["graph_analysis_v2"]["segments"]
    assert GraphAnalysis.model_validate(payload["graph_analysis_v2"]).point_count == len(payload["graph_points"])


@pytest.mark.parametrize(
    "payload",
    [
        {"expression": "x^2", "unknown": True},
        {"expression": "x^2", "interval": {"a": 1, "b": 1}},
        {"expression": "x^2", "interval": {"a": float("nan"), "b": 1}},
        {"expression": "x^2", "line": {"mode": "invalid"}},
        {"expression": "x^2", "line": {"mode": "intersect", "k": float("inf")}},
        {"expression": "x^2", "transform": {"type": "invalid", "value": 1}},
        {"expression": "x^2", "parameter_conditions": {"targets": ["invalid"]}},
        {"expression": "x^2", "parameter_conditions": {"targets": ["extrema_count"]}},
        {"expression": "x^2", "parameter_conditions": {"targets": ["increasing_r"], "extrema_count": 1}},
        {"expression": "x^2", "parameters": {"n": 1}},
        {"expression": "x^2", "parameter_mode": "substitute"},
    ],
)
def test_analyze_request_rejects_invalid_typed_options(payload):
    with pytest.raises(ValidationError):
        AnalyzeRequest.model_validate(payload)


def test_analyze_request_accepts_legacy_tool_payloads_and_exact_parameter():
    request = AnalyzeRequest.model_validate({
        "expression": "m*x^2",
        "parameters": {"m": "sqrt(2)"},
        "parameter_mode": "substitute",
        "interval": {"a": -2, "b": 2, "open_a": True},
        "line": {"mode": "tangent_at", "x0": 1, "k": 0, "b": 0},
        "transform": {"type": "absolute_all", "value": 1},
    })

    assert request.parameters is not None and request.parameters.m == "sqrt(2)"
    assert request.interval is not None and request.interval.open_a is True
    assert request.line is not None and request.line.mode.value == "tangent_at"
    assert request.transform is not None and request.transform.type.value == "absolute_all"


def test_graph_samples_request_rejects_unknown_parameters_and_invalid_window():
    with pytest.raises(ValidationError):
        GraphSamplesRequest.model_validate({"expression": "x", "parameters": {"n": 1}, "window": {"x_min": -1, "x_max": 1}})
    with pytest.raises(ValidationError):
        GraphSamplesRequest.model_validate({"expression": "x", "window": {"x_min": 2, "x_max": 1}})


def test_analyze_request_schema_exposes_strict_typed_components():
    schema = AnalyzeRequest.model_json_schema()

    assert schema["additionalProperties"] is False
    assert {"AnalysisInterval", "AnalysisLine", "ParameterConditionRequest", "PlotWindow"} - set(schema.get("$defs", {})) == {"PlotWindow"}
    assert schema["properties"]["interval"]["anyOf"][0]["$ref"].endswith("/AnalysisInterval")
    assert schema["properties"]["line"]["anyOf"][0]["$ref"].endswith("/AnalysisLine")


def test_analysis_steps_use_existing_evidence_without_upgrading_unknown():
    result = analyze_function("x^3 - 3*x")

    assert len(result["analysis_steps"]) == 11
    assert [step["order"] for step in result["analysis_steps"]] == list(range(1, 12))
    assert next(step for step in result["analysis_steps"] if step["key"] == "domain")["status"] == "complete"

    result["monotonicity_v2"]["status"] = "unknown"
    steps = build_analysis_steps(result)
    monotonicity = next(step for step in steps if step["key"] == "monotonicity")
    assert monotonicity["status"] == "unknown"

    result["monotonicity_v2"]["status"] = "partial"
    steps = build_analysis_steps(result)
    monotonicity = next(step for step in steps if step["key"] == "monotonicity")
    assert monotonicity["status"] == "partial"


def test_analysis_steps_exist_for_parameter_confirmation_without_running_solver():
    result = analyze_function("x^2 + m")

    assert result["analysis_mode"] == "requires_parameter_confirmation"
    assert len(result["analysis_steps"]) == 11
    assert all(step["status"] in {"unknown", "skipped"} for step in result["analysis_steps"])


def test_analysis_steps_exist_for_safe_symbolic_without_claiming_completion():
    result = analyze_function("x^2 + m", parameter_mode="symbolic")

    assert result["analysis_mode"] == "safe_symbolic"
    assert len(result["analysis_steps"]) == 11
    assert all(step["status"] == "unknown" for step in result["analysis_steps"])


def test_symbolic_parameter_cases_report_proven_root_and_asymptote_counts():
    result = analyze_function("x^2 + m*x", parameter_mode="symbolic")
    analysis = result["parameter_analysis_v2"]

    assert analysis["status"] == "complete"
    assert [boundary["exact"] for boundary in analysis["boundaries"]] == ["0"]
    assert {case["root_count"] for case in analysis["cases"]} == {1, 2}
    assert all(case["vertical_asymptote_count"] == 0 for case in analysis["cases"])
    assert all(case["verification"] in {"exact_boundary", "algebraic_invariant_interval"} for case in analysis["cases"])


def test_verification_report_backchecks_complete_analysis():
    result = _run_analyzer_job_sync("x^3 - 3*x", None, None, None, None, None)
    report = result["verification"]

    assert report["status"] == "verified"
    assert report["truncated"] is False
    assert report["possibly_incomplete"] is False
    assert {check["name"] for check in report["checks"]} == {
        "domain",
        "derivative_backcheck",
        "critical_point_membership",
        "monotonicity_components",
        "inflection_sign_change",
        "asymptote_limits",
        "intercept_substitution",
        "graph_domain_consistency",
    }
    assert all(check["status"] == "pass" for check in report["checks"])
    assert result["stage_statuses"]["verification"]["status"] == "ok"


def test_verification_report_detects_corrupted_derivative():
    result = analyze_function("x^2")
    result["derivative"] = "3*x"

    report = build_verification_report(result)
    derivative = next(check for check in report["checks"] if check["name"] == "derivative_backcheck")

    assert derivative["status"] == "fail"
    assert report["status"] == "failed"


def test_verification_report_detects_graph_point_outside_domain():
    result = analyze_function("sqrt(x)")
    _, _, _ = build_function_graph(result)
    result["graph_analysis_v2"]["segments"][0]["points"].append({"x": -1.0, "y": 0.0})

    report = build_verification_report(result)
    graph = next(check for check in report["checks"] if check["name"] == "graph_domain_consistency")

    assert graph["status"] == "fail"
    assert report["status"] == "failed"


def test_verification_report_marks_truncated_roots_partial():
    result = analyze_function("x^2 - 1")
    result["x_intercepts_v2"]["status"] = "partial"
    result["x_intercepts_v2"]["truncated"] = True

    report = build_verification_report(result)
    roots = next(check for check in report["checks"] if check["name"] == "intercept_substitution")

    assert roots["status"] == "warn"
    assert report["status"] == "partially_verified"
    assert report["truncated"] is True
    assert report["possibly_incomplete"] is True


def test_verification_report_checks_tangent_and_extrema_attainment():
    tangent = _run_analyzer_job_sync("x^2", None, None, {"mode": "tangent_at", "x0": 1}, None, None)
    extrema = _run_analyzer_job_sync("x^2", None, {"a": -1, "b": 1}, None, None, None)

    tangent_check = next(check for check in tangent["verification"]["checks"] if check["name"] == "tangent")
    extrema_check = next(check for check in extrema["verification"]["checks"] if check["name"] == "extrema_attainment")
    assert tangent_check["status"] == "pass"
    assert extrema_check["status"] == "pass"
