from __future__ import annotations

from dataclasses import dataclass

import sympy as sp


@dataclass(frozen=True)
class AlgebraTechnique:
    key: str
    title: str
    reason: str
    rule: str
    operation: str
    latex: str | None = None


def rational_parts(expression: sp.Expr, variable: sp.Symbol) -> tuple[sp.Expr, sp.Expr] | None:
    numerator, denominator = sp.fraction(sp.together(expression))
    if denominator == 1 or not denominator.has(variable):
        return None
    return sp.factor(numerator), sp.factor(denominator)


def factored_expression(expression: sp.Expr, variable: sp.Symbol) -> sp.Expr | None:
    try:
        poly = sp.Poly(expression, variable)
    except sp.PolynomialError:
        return None
    if poly.degree() < 2:
        return None
    factored = sp.factor(expression)
    return factored if sp.simplify(factored - expression) == 0 and factored != expression else None


def has_even_root_radical(expression: sp.Expr, variable: sp.Symbol) -> bool:
    return any(
        power.base.has(variable) and power.exp.is_Rational and power.exp.q % 2 == 0
        for power in expression.atoms(sp.Pow)
    )


def is_biquadratic(expression: sp.Expr, variable: sp.Symbol) -> bool:
    try:
        poly = sp.Poly(expression, variable)
    except sp.PolynomialError:
        return False
    powers = {monomial[0] for monomial in poly.monoms()}
    return bool(powers) and powers.issubset({0, 2, 4}) and 4 in powers


def has_rational_root_division_path(expression: sp.Expr, variable: sp.Symbol) -> bool:
    try:
        poly = sp.Poly(expression, variable)
    except sp.PolynomialError:
        return False
    if poly.degree() < 3:
        return False
    roots = sp.roots(poly.as_expr(), variable)
    return any(root.is_rational for root in roots)


def polynomial_division_by_root(expression: sp.Expr, variable: sp.Symbol, root: sp.Expr) -> tuple[sp.Expr, sp.Expr]:
    quotient, remainder = sp.div(sp.Poly(expression, variable), sp.Poly(variable - root, variable))
    return sp.factor(quotient.as_expr()), sp.factor(remainder.as_expr())


def detect_primary_technique(topic: str, expression: sp.Expr, variable: sp.Symbol, rel_op: str | None = None) -> AlgebraTechnique:
    rational = rational_parts(expression, variable)
    if topic == "inequality":
        return AlgebraTechnique(
            key="sign_chart",
            title="Chọn phương pháp xét dấu",
            reason="Bất phương trình một biến nên đưa về một vế rồi lập bảng xét dấu theo các mốc tới hạn.",
            rule="Xét dấu biểu thức",
            operation="Tìm nghiệm tử số, điểm làm mẫu không xác định, thử dấu từng khoảng.",
            latex=sp.latex(_relation_from_expression(expression, rel_op or ">")),
        )
    if rational:
        numerator, denominator = rational
        return AlgebraTechnique(
            key="clear_denominator",
            title="Chọn phương pháp khử mẫu",
            reason="Phương trình có phân thức theo biến, nên phải giữ điều kiện mẫu khác 0 rồi giải tử số.",
            rule="Phân thức bằng 0",
            operation="Quy đồng, khử mẫu, giải tử số và lọc nghiệm làm mẫu bằng 0.",
            latex=rf"{sp.latex(denominator)}\ne 0,\quad {sp.latex(numerator)}=0",
        )
    if has_even_root_radical(expression, variable):
        return AlgebraTechnique(
            key="radical_isolation",
            title="Chọn phương pháp xử lý căn",
            reason="Phương trình có căn chẵn nên cần đặt điều kiện, cô lập căn rồi bình phương.",
            rule="Cô lập căn và bình phương",
            operation="Ghi điều kiện căn không âm, biến đổi về phương trình không còn căn và thử lại nghiệm.",
            latex=sp.latex(expression),
        )
    if is_biquadratic(expression, variable):
        return AlgebraTechnique(
            key="substitution",
            title="Chọn phương pháp đặt ẩn phụ",
            reason="Đa thức chỉ có các lũy thừa chẵn nên đặt t = x^2 để giảm bậc.",
            rule="Đặt ẩn phụ",
            operation="Đặt t = x^2, giải phương trình theo t, rồi đổi ngược về x.",
            latex=r"t=x^2",
        )
    if has_rational_root_division_path(expression, variable):
        return AlgebraTechnique(
            key="polynomial_division",
            title="Chọn phương pháp chia đa thức",
            reason="Đa thức bậc cao có nghiệm hữu tỉ, nên tách nhân tử bằng phép chia đa thức.",
            rule="Định lý nghiệm hữu tỉ",
            operation="Tìm nghiệm hữu tỉ r, chia P(x) cho x-r, rồi giải phần còn lại.",
            latex=sp.latex(expression),
        )
    factored = factored_expression(expression, variable)
    if factored is not None:
        return AlgebraTechnique(
            key="factor",
            title="Chọn phương pháp phân tích nhân tử",
            reason="Đa thức phân tích được thành tích, nên dùng quy tắc tích bằng 0.",
            rule="Tích bằng 0",
            operation="Phân tích nhân tử rồi cho từng nhân tử bằng 0.",
            latex=sp.latex(factored),
        )
    return AlgebraTechnique(
        key="symbolic_solve",
        title="Chọn phương pháp giải trực tiếp",
        reason="Chưa nhận ra kỹ thuật đặc biệt, nên giải biểu thức một vế rồi kiểm tra lại kết quả.",
        rule="Giải symbolic và kiểm chứng",
        operation="Giải trên miền đã chọn, sau đó thay nghiệm vào đề gốc.",
        latex=sp.latex(expression),
    )


def _relation_from_expression(expression: sp.Expr, rel_op: str) -> sp.Relational:
    if rel_op == ">":
        return sp.Gt(expression, 0, evaluate=False)
    if rel_op == ">=":
        return sp.Ge(expression, 0, evaluate=False)
    if rel_op == "<":
        return sp.Lt(expression, 0, evaluate=False)
    return sp.Le(expression, 0, evaluate=False)
