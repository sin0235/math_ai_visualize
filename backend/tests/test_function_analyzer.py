from app.services.function_analyzer import analyze_function
from app.services.function_graph_builder import build_function_graph


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
