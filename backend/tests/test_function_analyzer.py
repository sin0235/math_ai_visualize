from app.services.function_analyzer import analyze_function


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
