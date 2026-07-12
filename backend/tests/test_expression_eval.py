import math

import pytest

from app.services.expression_eval import UnsafeExpressionError, safe_eval, safe_eval_exact, safe_sympify, try_safe_eval, try_safe_eval_exact


def test_basic_arithmetic():
    assert safe_eval("1 + 2") == 3.0
    assert safe_eval("3 * 4 - 1") == 11.0
    assert safe_eval("(1 + 2) * 3") == 9.0
    assert safe_eval("2 ** 10") == 1024.0
    assert safe_eval("7 / 2") == 3.5


def test_constants():
    assert safe_eval("pi") == pytest.approx(math.pi)
    assert safe_eval("e") == pytest.approx(math.e)


def test_functions_and_radians():
    assert safe_eval("sqrt(9)") == 3.0
    assert safe_eval("sin(0)") == pytest.approx(0.0)
    assert safe_eval("cos(0)") == pytest.approx(1.0)
    assert safe_eval("rad(180)") == pytest.approx(math.pi)
    assert safe_eval("sin(rad(90))") == pytest.approx(1.0)


def test_variables():
    assert safe_eval("a/2", {"a": 6}) == 3.0
    assert safe_eval("sqrt(3)*a/2", {"a": 2}) == pytest.approx(math.sqrt(3))
    assert safe_eval("h*sin(rad(alpha))", {"h": 4, "alpha": 30}) == pytest.approx(2.0)


def test_unknown_variable_rejected():
    with pytest.raises(UnsafeExpressionError):
        safe_eval("a + b", {"a": 1})


def test_disallowed_function_rejected():
    with pytest.raises(UnsafeExpressionError):
        safe_eval("__import__('os')")
    with pytest.raises(UnsafeExpressionError):
        safe_eval("open('x')")


def test_disallowed_attribute_rejected():
    with pytest.raises(UnsafeExpressionError):
        safe_eval("(1).bit_length()")


def test_lambda_and_comprehension_rejected():
    with pytest.raises(UnsafeExpressionError):
        safe_eval("(lambda: 1)()")
    with pytest.raises(UnsafeExpressionError):
        safe_eval("[x for x in range(3)]")


def test_division_by_zero_returns_unsafe():
    with pytest.raises(UnsafeExpressionError):
        safe_eval("1/0")


def test_power_requires_small_literal_exponent():
    assert safe_eval("2 ** 10") == 1024.0
    assert safe_eval("pow(2, 10)") == 1024.0
    for expression in ["2 ** 65", "pow(2, 65)", "2 ** a", "pow(2, a)"]:
        with pytest.raises(UnsafeExpressionError):
            safe_eval(expression, {"a": 2})


def test_safe_eval_interprets_allowed_ast_without_python_eval():
    assert safe_eval("max(a, 3) if a > 0 else abs(a)", {"a": 4}) == 4.0
    assert safe_eval("min(2, 3) and 7") == 7.0
    assert safe_eval("1 < 2 < 3") == 1.0


def test_try_safe_eval_returns_none_on_error():
    assert try_safe_eval("a + 1", {}) is None
    assert try_safe_eval("a + 1", {"a": 4}) == 5.0
    assert try_safe_eval("garbage??", {}) is None


def test_safe_sympify_exact_values():
    expr, value = safe_eval_exact("sqrt(3)/2")
    assert str(expr) == "sqrt(3)/2"
    assert value == pytest.approx(math.sqrt(3) / 2)
    assert str(safe_eval_exact("sin(pi/6)")[0]) == "1/2"
    assert safe_eval_exact("sqrt(2)**2")[0] == 2
    assert safe_eval_exact("a/2", {"a": 6}) == (3, 3.0)
    assert str(safe_sympify("a/2", {"a": "sqrt(2)"})) == "sqrt(2)/2"
    assert try_safe_eval_exact("a + 1", {}) is None


def test_safe_sympify_rejects_unsafe_syntax():
    for expr in ["__import__('os')", "(1).__class__", "[1, 2]", "{'x': 1}", "(lambda: 1)()"]:
        with pytest.raises(UnsafeExpressionError):
            safe_eval_exact(expr)


def test_apply_parameters_to_scene_evaluates_expressions():
    from app.services.extractor import apply_parameters_to_scene

    data = {
        "parameters": [
            {"name": "a", "default": 4, "min": 1, "max": 8, "step": 0.5},
            {"name": "h", "default": 5, "min": 1, "max": 10, "step": 0.5},
        ],
        "objects": [
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 0, "y": 0, "z": 0, "x_expr": "a"},
            {"type": "point_3d", "name": "S", "x": 0, "y": 0, "z": 0, "y_expr": "h"},
            {"type": "sphere", "center": "A", "radius": 0, "radius_expr": "a/2"},
        ],
    }
    apply_parameters_to_scene(data)

    assert data["objects"][1]["x"] == 4.0
    assert data["objects"][2]["y"] == 5.0
    assert data["objects"][3]["radius"] == 2.0


def test_apply_parameters_skips_when_no_parameters():
    from app.services.extractor import apply_parameters_to_scene

    data = {
        "parameters": [],
        "objects": [
            {"type": "point_2d", "name": "A", "x": 1, "y": 2, "x_expr": "a"},
        ],
    }
    apply_parameters_to_scene(data)
    assert data["objects"][0]["x"] == 1


def test_normalize_scene_json_full_flow_with_parameters():
    """E2E: scene LLM-style với biến tổng quát a, h → normalize_scene_json
    phải eval được toạ độ default và parameters phải hợp lệ."""
    from app.schemas.scene import MathScene
    from app.services.extractor import normalize_scene_json

    raw = {
        "problem_text": "Hình chóp S.ABCD đáy vuông cạnh a, SA = h",
        "renderer": "threejs_3d",
        "topic": "solid_geometry",
        "view": {"dimension": "3d", "show_axes": True, "show_grid": True},
        "parameters": [
            {"name": "a", "default": 3, "min": 1, "max": 8, "step": 0.5},
            {"name": "h", "default": 3, "min": 1, "max": 8, "step": 0.5},
        ],
        "objects": [
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 0, "y": 0, "z": 0, "x_expr": "a"},
            {"type": "point_3d", "name": "C", "x": 0, "y": 0, "z": 0, "x_expr": "a", "z_expr": "a"},
            {"type": "point_3d", "name": "D", "x": 0, "y": 0, "z": 0, "z_expr": "a"},
            {"type": "point_3d", "name": "S", "x": 0, "y": 0, "z": 0, "y_expr": "h"},
            {"type": "segment", "points": ["S", "A"]},
            {"type": "segment", "points": ["A", "B"]},
            {"type": "segment", "points": ["B", "C"]},
            {"type": "segment", "points": ["C", "D"]},
            {"type": "segment", "points": ["D", "A"]},
        ],
        "annotations": [],
    }

    normalized = normalize_scene_json(raw)
    scene = MathScene.model_validate(normalized)

    points = {p.name: p for p in scene.objects if p.type == "point_3d"}
    assert points["A"].x == 0 and points["A"].y == 0 and points["A"].z == 0
    assert points["B"].x == 3.0
    assert points["C"].x == 3.0 and points["C"].z == 3.0
    assert points["D"].z == 3.0
    assert points["S"].y == 3.0

    assert len(scene.parameters) == 2
    by_name = {p.name: p for p in scene.parameters}
    assert by_name["a"].default == 3.0
    assert by_name["a"].min == 1.0
    assert by_name["a"].max == 8.0
    assert by_name["h"].step == 0.5


def test_normalize_scene_json_drops_invalid_parameter():
    """Parameter thiếu name hoặc default phải bị loại bỏ, không làm crash."""
    from app.services.extractor import normalize_scene_json

    raw = {
        "problem_text": "demo",
        "renderer": "threejs_3d",
        "topic": "solid_geometry",
        "view": {"dimension": "3d"},
        "parameters": [
            {"name": "a", "default": 4},
            {"name": "", "default": 1},
            {"default": 2},
            "not-a-dict",
        ],
        "objects": [
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0, "x_expr": "a"},
        ],
        "annotations": [],
    }
    normalized = normalize_scene_json(raw)
    assert len(normalized["parameters"]) == 1
    assert normalized["parameters"][0]["name"] == "a"
    assert normalized["objects"][0]["x"] == 4.0
