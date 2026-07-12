import asyncio
import json

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError

from app.main import app, http_exception_handler, request_validation_exception_handler
from app.schemas.analysis import AnalyzeResponse, CriticalPoint, VariationRow


def _iter_api_routes(routes):
    """Walk FastAPI routes including 0.139+ `_IncludedRouter` wrappers."""
    for route in routes:
        path = getattr(route, "path", None)
        if path is not None:
            yield route
            continue
        original = getattr(route, "original_router", None)
        if original is not None:
            yield from _iter_api_routes(original.routes)
            continue
        nested = getattr(route, "routes", None)
        if nested is not None:
            yield from _iter_api_routes(nested)


def test_split_solve_and_analysis_routes_stay_registered():
    paths = {route.path for route in _iter_api_routes(app.routes)}

    assert "/api/solve" in paths
    assert "/api/analyze" in paths
    assert "/api/analyze/ocr" in paths
    assert "/api/analyzer/analyze" in paths
    assert "/api/analyzer/history" in paths
    assert "/api/analyzer/export" in paths
    assert {
        "/api/analyzer/tools/interval-extrema",
        "/api/analyzer/tools/line",
        "/api/analyzer/tools/tangent",
        "/api/analyzer/tools/transform",
        "/api/analyzer/tools/parameter",
    } <= paths


def test_solve_and_analysis_routes_have_separate_tags():
    route_tags = {
        route.path: getattr(route, "tags", [])
        for route in _iter_api_routes(app.routes)
        if getattr(route, "path", None) in {"/api/solve", "/api/analyze", "/api/analyze/ocr"}
    }

    assert route_tags["/api/solve"] == ["solver"]
    assert route_tags["/api/analyze"] == ["function-analysis"]
    assert route_tags["/api/analyze/ocr"] == ["function-analysis"]


def test_analysis_response_list_defaults_are_independent():
    first = AnalyzeResponse(expression="x")
    second = AnalyzeResponse(expression="x^2")

    first.critical_points.append(CriticalPoint(x="0", x_exact="0", y="0", kind="min", kind_label="Cực tiểu"))
    first.variation_table.append(VariationRow(x="0", y="0", kind="min"))
    first.warnings.append("first-only")

    assert second.critical_points == []
    assert second.variation_table == []
    assert second.warnings == []


def test_analysis_response_keeps_frontend_contract_field_names():
    payload = AnalyzeResponse(
        expression="x^2",
        range_val="[0, +oo)",
        graph_scene={"objects": []},
        graph_points=[{"x": 0.0, "y": 0.0}],
        ocr_text="y=x^2",
        ocr_expression="x^2",
        interval_analysis={"conclusion": "ok"},
        line_analysis={"intersection_count": 1},
        parameter_conditions=[{"label": "m"}],
        transform_preview={
            "type": "vertical_shift",
            "value": "1",
            "label": "f(x) + 1",
            "expression": "x**2 + 1",
            "expression_latex": "x^{2} + 1",
            "convention": "a>0: dịch lên; a<0: dịch xuống",
            "expression_template": "g(x)=f(x)+a",
            "requires_value": True,
            "invariants": ["domain", "shape"],
            "anchors": [],
        },
        capabilities={"mode": "symbolic"},
    ).model_dump(mode="json")

    for key in [
        "range_val",
        "variation_table",
        "graph_scene",
        "graph_points",
        "ocr_text",
        "ocr_expression",
        "interval_analysis",
        "line_analysis",
        "parameter_conditions",
        "transform_preview",
        "capabilities",
    ]:
        assert key in payload


def test_analyzer_openapi_uses_strict_typed_components():
    schema = app.openapi()
    body = schema["paths"]["/api/analyze"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    session_body = schema["paths"]["/api/analyzer/analyze"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    tool_body = schema["paths"]["/api/analyzer/tools/interval-extrema"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    components = schema["components"]["schemas"]

    assert body["$ref"].endswith("/AnalyzeRequest")
    assert session_body["$ref"].endswith("/AnalyzerBaseRequest")
    assert tool_body["$ref"].endswith("/AnalyzerIntervalToolRequest")
    for name in [
        "AnalysisInterval",
        "AnalysisLine",
        "ParameterConditionRequest",
        "PlotWindow",
        "ValuedGraphTransform",
        "FixedGraphTransform",
        "GraphAnalysis",
        "AnalyzerBaseRequest",
        "AnalyzerIntervalToolRequest",
    ]:
        assert components[name]["additionalProperties"] is False
    assert components["AnalyzerValidationError"]["properties"]["detail"]["properties"]["code"]["example"] == "ANALYZER_INPUT_INVALID"
    assert schema["paths"]["/api/analyze"]["post"]["responses"]["422"]["content"]["application/json"]["schema"]["$ref"].endswith("/AnalyzerValidationError")
    assert "401" in schema["paths"]["/api/analyzer/history"]["get"]["responses"]


def test_openapi_derives_auth_and_origin_responses_from_dependencies():
    schema = app.openapi()

    protected = schema["paths"]["/api/render/v3"]["post"]["responses"]
    telemetry = schema["paths"]["/api/telemetry/client-error"]["post"]["responses"]
    analyzer = schema["paths"]["/api/analyze"]["post"]["responses"]
    algebra = schema["paths"]["/api/algebra/solve"]["post"]["responses"]
    public = schema["paths"]["/api/health"]["get"]["responses"]

    assert {"401", "403"} <= set(protected)
    assert "403" in telemetry
    assert {"404", "429"} <= set(analyzer)
    assert {"400", "401", "429", "503", "504"} <= set(algebra)
    assert "401" not in public


def test_analyzer_validation_error_has_safe_typed_envelope():
    request = Request({
        "type": "http",
        "method": "POST",
        "path": "/api/analyze",
        "headers": [],
        "query_string": b"",
        "server": ("test", 80),
        "client": ("test", 1),
        "scheme": "http",
        "root_path": "",
    })
    response = asyncio.run(request_validation_exception_handler(request, RequestValidationError([{"secret": "raw"}])))
    payload = json.loads(response.body)

    assert response.status_code == 422
    assert payload["detail"] == {
        "code": "ANALYZER_INPUT_INVALID",
        "message": "Dữ liệu yêu cầu phân tích không hợp lệ.",
        "correlation_id": "",
        "stage": "request",
        "retryable": False,
    }
    assert "raw" not in response.body.decode()


def test_analyzer_rate_limit_uses_analyzer_error_code():
    request = Request({
        "type": "http",
        "method": "POST",
        "path": "/api/analyze",
        "headers": [],
        "query_string": b"",
        "server": ("test", 80),
        "client": ("test", 1),
        "scheme": "http",
        "root_path": "",
    })
    response = asyncio.run(http_exception_handler(request, HTTPException(status_code=429, detail="rate limited", headers={"Retry-After": "3"})))
    payload = json.loads(response.body)

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "3"
    assert payload["detail"]["code"] == "ANALYZER_RATE_LIMITED"
    assert payload["detail"]["retryable"] is True
