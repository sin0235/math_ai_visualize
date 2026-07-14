from __future__ import annotations

import sympy as sp
from sympy.printing.latex import LatexPrinter
from sympy.printing.str import StrPrinter


class _DisplayLog(sp.Function):
    """Nút chỉ dùng khi xuất kết quả, không tham gia tính toán symbolic."""

    nargs = 2


class _AlgebraLatexPrinter(LatexPrinter):
    def _print_log(self, expression: sp.Expr, exp: str | None = None) -> str:
        argument = self._print(expression.args[0])
        rendered = rf"\ln{{\left({argument} \right)}}"
        return self._do_exponent(rendered, exp)

    def _print__DisplayLog(self, expression: sp.Expr, exp: str | None = None) -> str:
        argument = self._print(expression.args[0])
        base = self._print(expression.args[1])
        rendered = rf"\log_{{{base}}}{{\left({argument} \right)}}"
        return self._do_exponent(rendered, exp)


class _AlgebraStrPrinter(StrPrinter):
    def _print_log(self, expression: sp.Expr) -> str:
        return f"ln({self._print(expression.args[0])})"

    def _print__DisplayLog(self, expression: sp.Expr) -> str:
        argument = self._print(expression.args[0])
        base = self._print(expression.args[1])
        return f"log_{base}({argument})"


_LATEX_PRINTER = _AlgebraLatexPrinter()
_STR_PRINTER = _AlgebraStrPrinter()


def algebra_latex(expression: object) -> str:
    if not isinstance(expression, sp.Basic):
        return str(expression)
    return _LATEX_PRINTER.doprint(_prepare_for_print(expression))


def algebra_text(expression: object) -> str:
    if not isinstance(expression, sp.Basic):
        return str(expression)
    return _STR_PRINTER.doprint(_prepare_for_print(expression))


def _prepare_for_print(expression: sp.Basic) -> sp.Basic:
    prepared = sp.expand_mul(expression) if isinstance(expression, sp.Expr) and _has_inverse_log(expression) else expression
    return _rewrite_log_ratios(prepared)


def _has_inverse_log(expression: sp.Basic) -> bool:
    return any(
        isinstance(node, sp.Pow)
        and node.exp == -1
        and node.base.func is sp.log
        for node in sp.preorder_traversal(expression)
    )


def _rewrite_log_ratios(expression: sp.Basic) -> sp.Basic:
    return expression.replace(_contains_log_ratio, _to_display_log)


def _contains_log_ratio(expression: sp.Basic) -> bool:
    if not expression.is_Mul:
        return False
    factors = sp.Mul.make_args(expression)
    return bool(_numerator_logs(factors) and _denominator_logs(factors))


def _to_display_log(expression: sp.Basic) -> sp.Basic:
    factors = list(sp.Mul.make_args(expression))
    numerator = _numerator_logs(factors)[0]
    denominator = _denominator_logs(factors)[0]
    factors.remove(numerator)
    factors.remove(denominator)
    base_log = denominator.base
    return sp.Mul(*factors, _DisplayLog(numerator.args[0], base_log.args[0]))


def _numerator_logs(factors: tuple[sp.Expr, ...] | list[sp.Expr]) -> list[sp.Expr]:
    return [factor for factor in factors if factor.func is sp.log and len(factor.args) == 1]


def _denominator_logs(factors: tuple[sp.Expr, ...] | list[sp.Expr]) -> list[sp.Pow]:
    return [
        factor
        for factor in factors
        if isinstance(factor, sp.Pow)
        and factor.exp == -1
        and factor.base.func is sp.log
        and len(factor.base.args) == 1
    ]
