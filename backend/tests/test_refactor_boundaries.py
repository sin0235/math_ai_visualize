from app.main import app
from app.schemas.analysis import AnalyzeResponse, CriticalPoint, VariationRow


def test_split_solve_and_analysis_routes_stay_registered():
    paths = {route.path for route in app.routes}

    assert "/api/solve" in paths
    assert "/api/analyze" in paths
    assert "/api/analyze/ocr" in paths


def test_solve_and_analysis_routes_have_separate_tags():
    route_tags = {route.path: getattr(route, "tags", []) for route in app.routes if route.path in {"/api/solve", "/api/analyze", "/api/analyze/ocr"}}

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
        transform_preview={"type": "vertical_shift"},
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
