from __future__ import annotations

from dataclasses import dataclass

import sympy as sp

from app.schemas.algebra import AlgebraSolveStep
from app.services.algebra.formatting import solution_values
from app.services.algebra.parser import ParsedAlgebraProblem


@dataclass(frozen=True)
class ExpLogTemplateResult:
    solution_set: sp.Set
    values: list[sp.Expr] | None
    steps: list[AlgebraSolveStep]


@dataclass(frozen=True)
class LogTerm:
    arg: sp.Expr
    base: sp.Expr
    coefficient: sp.Expr


def solve_exp_log_template(problem: ParsedAlgebraProblem, start_index: int) -> ExpLogTemplateResult | None:
    if problem.relation is None or not isinstance(problem.relation, sp.Equality):
        return None
    variable = problem.variable
    return (
        _same_base_exponential_template(problem, variable, start_index)
        or _linear_log_template(problem, variable, start_index)
        or _single_exponential_log_template(problem, variable, start_index)
        or _exponential_substitution_template(problem, variable, start_index)
    )


def _same_base_exponential_template(problem: ParsedAlgebraProblem, variable: sp.Symbol, start_index: int) -> ExpLogTemplateResult | None:
    relation = problem.relation
    if relation is None:
        return None
    left = _as_power_with_base(relation.lhs, variable)
    right = _as_power_with_base(relation.rhs, variable)
    if left is None or right is None:
        return None
    base_left, exp_left = left
    base_right, exp_right = right
    if sp.simplify(base_left - base_right) != 0:
        return None
    exponent_equation = sp.Eq(exp_left, exp_right, evaluate=False)
    solution_set = _solve_and_filter(exponent_equation.lhs - exponent_equation.rhs, problem)
    values = solution_values(solution_set)
    steps = [
        AlgebraSolveStep(
            index=start_index,
            title="Chọn phương pháp cùng cơ số",
            explanation="Hai vế là lũy thừa cùng cơ số dương khác 1 nên so sánh số mũ.",
            short_explanation="Đưa hai vế về cùng cơ số rồi so sánh số mũ.",
            detail_level="brief",
            method="same_base_exponential",
            goal="Biến phương trình mũ thành phương trình theo số mũ.",
            why="Nếu a > 0, a khác 1 và a^u = a^v thì u = v.",
            rule="Cùng cơ số",
            operation="Viết hai vế dưới dạng cùng cơ số rồi cho hai số mũ bằng nhau.",
            before_latex=sp.latex(relation),
            after_latex=sp.latex(exponent_equation),
            pitfall="Không dùng quy tắc này nếu cơ số không cùng nhau hoặc cơ số không hợp lệ.",
            check="Lũy thừa sau khi đổi cơ số phải đúng với hai vế ban đầu.",
            result_latex=sp.latex(exponent_equation),
            kind="transform",
            confidence="symbolic",
        ),
        AlgebraSolveStep(
            index=start_index + 1,
            title="Giải phương trình số mũ",
            explanation="Giải phương trình thu được từ việc so sánh hai số mũ.",
            short_explanation="Giải phương trình giữa hai số mũ.",
            detail_level="standard",
            method="solve_exponent_equation",
            goal="Tìm nghiệm của biến.",
            why="Sau khi cùng cơ số, bài toán trở thành phương trình đại số đơn giản hơn.",
            rule="Giải phương trình đại số",
            operation="Giải phương trình giữa hai số mũ.",
            before_latex=sp.latex(exponent_equation),
            after_latex=_values_latex(variable, values),
            pitfall="Nếu có điều kiện miền nghiệm, vẫn phải kiểm tra lại.",
            check="Thay nghiệm vào phương trình mũ ban đầu.",
            result="; ".join(sp.sstr(value) for value in values or []),
            result_latex=_values_latex(variable, values),
            kind="solve",
            confidence="symbolic",
        ),
    ]
    return ExpLogTemplateResult(solution_set=solution_set, values=values, steps=steps)


def _linear_log_template(problem: ParsedAlgebraProblem, variable: sp.Symbol, start_index: int) -> ExpLogTemplateResult | None:
    relation = problem.relation
    if relation is None:
        return None
    expression = sp.expand(relation.lhs - relation.rhs)
    terms = sp.Add.make_args(expression)
    log_terms: list[LogTerm] = []
    other_terms: list[sp.Expr] = []
    for term in terms:
        parsed = _log_term(term, variable)
        if parsed is None:
            other_terms.append(term)
        else:
            log_terms.append(parsed)
    if not log_terms:
        return None
    if any(term.has(variable) for term in other_terms):
        return None
    base = log_terms[0].base
    if any(sp.simplify(item.base - base) != 0 for item in log_terms):
        return None
    if any(item.coefficient.has(variable) for item in log_terms):
        return None
    if any(not item.coefficient.is_Rational for item in log_terms):
        return None
    constant = sp.simplify(sum(other_terms))
    log_rhs = sp.simplify(-constant)
    combined_arg = sp.factor(sp.prod(item.arg ** item.coefficient for item in log_terms))
    algebra_equation = sp.Eq(combined_arg, sp.Pow(base, log_rhs, evaluate=False), evaluate=False)
    solution_set = _solve_and_filter(algebra_equation.lhs - algebra_equation.rhs, problem)
    values = solution_values(solution_set)
    title = _log_method_title(log_terms, constant)
    steps = [
        AlgebraSolveStep(
            index=start_index,
            title=title,
            explanation="Dùng tính chất logarit cùng cơ số để gom các log về một log duy nhất.",
            short_explanation="Gộp/tách log cùng cơ số để còn một log.",
            detail_level="brief",
            method="combine_logarithms",
            goal="Đưa phương trình log về dạng log_a(F(x)) = c.",
            why="Khi các biểu thức trong log dương, tổng/trừ/hệ số log có thể chuyển thành tích, thương hoặc lũy thừa bên trong log.",
            rule="Tính chất logarit",
            operation="Gộp các hạng log cùng cơ số và chuyển hằng số sang vế phải.",
            before_latex=sp.latex(relation),
            after_latex=sp.latex(sp.Eq(sp.log(combined_arg) / sp.log(base), log_rhs, evaluate=False)),
            pitfall="Chỉ gộp log sau khi đã giữ điều kiện các biểu thức trong log lớn hơn 0.",
            check="Điều kiện xác định phải được dùng để lọc nghiệm sau khi giải.",
            expression=sp.sstr(expression),
            expression_latex=sp.latex(expression),
            result=sp.sstr(combined_arg),
            result_latex=sp.latex(combined_arg),
            kind="transform",
            confidence="symbolic",
        ),
        AlgebraSolveStep(
            index=start_index + 1,
            title="Bỏ log",
            explanation="Dùng định nghĩa logarit để chuyển phương trình về đại số.",
            short_explanation="log_a(F)=c tương đương F=a^c.",
            detail_level="standard",
            method="log_definition",
            goal="Tìm phương trình không còn log.",
            why="log_a(F)=c tương đương F=a^c khi F>0, a>0 và a khác 1.",
            rule="Định nghĩa logarit",
            operation="Cho biểu thức trong log bằng lũy thừa của cơ số.",
            before_latex=sp.latex(sp.Eq(sp.log(combined_arg) / sp.log(base), log_rhs, evaluate=False)),
            after_latex=sp.latex(algebra_equation),
            pitfall="Bước bỏ log chỉ cho nghiệm ứng viên; vẫn phải thử điều kiện log.",
            check="Thay nghiệm vào từng log ban đầu để kiểm tra.",
            expression=sp.sstr(combined_arg),
            expression_latex=sp.latex(combined_arg),
            result=sp.sstr(algebra_equation.rhs),
            result_latex=sp.latex(algebra_equation),
            kind="transform",
            confidence="symbolic",
        ),
        AlgebraSolveStep(
            index=start_index + 2,
            title="Giải phương trình đại số",
            explanation="Giải phương trình sau khi đã bỏ log.",
            short_explanation="Giải phương trình không còn log rồi lấy nghiệm ứng viên.",
            detail_level="standard",
            method="solve_algebraic_after_log",
            goal="Tìm nghiệm ứng viên trước khi lọc điều kiện.",
            why="Sau khi bỏ log, bài toán trở về phương trình đại số theo biến ban đầu.",
            rule="Giải phương trình đại số",
            operation="Giải phương trình thu được và giữ các nghiệm thỏa đề gốc.",
            before_latex=sp.latex(algebra_equation),
            after_latex=_values_latex(variable, values),
            pitfall="Nghiệm làm biểu thức trong log không dương phải bị loại.",
            check="Đối chiếu từng nghiệm với điều kiện xác định của log.",
            result="; ".join(sp.sstr(value) for value in values or []),
            result_latex=_values_latex(variable, values),
            kind="solve",
            confidence="symbolic",
        ),
        AlgebraSolveStep(
            index=start_index + 3,
            title="Thử lại điều kiện log",
            explanation="Giữ những nghiệm làm tất cả biểu thức trong log dương và thỏa phương trình ban đầu.",
            short_explanation="Lọc nghiệm bằng điều kiện log và thay lại đề gốc.",
            detail_level="standard",
            method="log_domain_check",
            goal="Loại nghiệm không hợp lệ do điều kiện log.",
            why="Logarit chỉ xác định khi biểu thức bên trong lớn hơn 0.",
            rule="Thay lại nghiệm",
            operation="Thay từng nghiệm ứng viên vào phương trình ban đầu.",
            before_latex=sp.latex(relation),
            after_latex=_values_latex(variable, values),
            pitfall="Không được chỉ giải phương trình sau khi bỏ log rồi kết luận.",
            check="Mọi nghiệm cuối cùng phải làm từng log có nghĩa.",
            result="; ".join(sp.sstr(value) for value in values or []),
            result_latex=_values_latex(variable, values),
            kind="verify",
            confidence="verified",
        ),
    ]
    return ExpLogTemplateResult(solution_set=solution_set, values=values, steps=steps)


def _single_exponential_log_template(problem: ParsedAlgebraProblem, variable: sp.Symbol, start_index: int) -> ExpLogTemplateResult | None:
    relation = problem.relation
    if relation is None:
        return None
    left_power = _as_power_with_base(relation.lhs, variable)
    right_power = _as_power_with_base(relation.rhs, variable)
    if left_power is not None and not relation.rhs.has(variable):
        base, exponent = left_power
        target = relation.rhs
    elif right_power is not None and not relation.lhs.has(variable):
        base, exponent = right_power
        target = relation.lhs
    else:
        return None
    if _is_positive(target) is False:
        return None
    log_equation = sp.Eq(exponent, sp.log(target) / sp.log(base), evaluate=False)
    solution_set = _solve_and_filter(log_equation.lhs - log_equation.rhs, problem)
    values = solution_values(solution_set)
    return ExpLogTemplateResult(
        solution_set=solution_set,
        values=values,
        steps=[
            AlgebraSolveStep(
                index=start_index,
                title="Lấy log hai vế",
                explanation="Hai vế không đưa được về cùng cơ số đẹp, nên lấy log hai vế để kéo số mũ xuống.",
                short_explanation="Lấy log hai vế để đưa số mũ xuống.",
                detail_level="brief",
                method="log_both_sides",
                goal="Biến phương trình mũ thành phương trình theo số mũ.",
                why="Nếu a^u = b với a > 0, a khác 1 và b > 0 thì u = log(b)/log(a).",
                rule="Logarit hai vế",
                operation="Dùng công thức a^u=b tương đương u=log(b)/log(a).",
                before_latex=sp.latex(relation),
                after_latex=sp.latex(log_equation),
                pitfall="Chỉ lấy log hai vế khi hai vế dương.",
                check="Thay nghiệm vào phương trình mũ ban đầu.",
                result_latex=sp.latex(log_equation),
                kind="transform",
                confidence="symbolic",
            ),
            AlgebraSolveStep(
                index=start_index + 1,
                title="Giải phương trình sau khi lấy log",
                explanation="Giải phương trình theo biến sau khi số mũ đã được đưa xuống.",
                short_explanation="Giải phương trình thu được sau khi lấy log.",
                detail_level="standard",
                method="solve_after_log_both_sides",
                goal="Tìm nghiệm của biến.",
                why="Bài toán đã trở thành phương trình đại số/log đơn giản theo biến.",
                rule="Giải phương trình",
                operation="Giải phương trình số mũ đã hạ xuống.",
                before_latex=sp.latex(log_equation),
                after_latex=_values_latex(variable, values),
                pitfall="Nếu kết quả là log, nên giữ dạng chính xác thay vì làm tròn sớm.",
                check="Thay nghiệm vào phương trình ban đầu để kiểm tra.",
                result="; ".join(sp.sstr(value) for value in values or []),
                result_latex=_values_latex(variable, values),
                kind="solve",
                confidence="symbolic",
            ),
        ],
    )


def _exponential_substitution_template(problem: ParsedAlgebraProblem, variable: sp.Symbol, start_index: int) -> ExpLogTemplateResult | None:
    relation = problem.relation
    if relation is None:
        return None
    expression = sp.expand(relation.lhs - relation.rhs)
    base = _single_exponential_base(expression, variable)
    if base is None:
        return None
    t = sp.Symbol("t", positive=True)
    rewritten = _replace_base_power(expression, variable, base, t)
    if rewritten is None:
        return None
    numerator, denominator = sp.fraction(sp.together(rewritten))
    try:
        poly = sp.Poly(sp.expand(numerator), t)
    except sp.PolynomialError:
        return None
    if poly.degree() < 1:
        return None
    t_solution_set = sp.solveset(poly.as_expr(), t, domain=sp.S.Reals)
    t_values = solution_values(t_solution_set) or []
    positive_t_values = [sp.simplify(value) for value in t_values if _is_positive(value)]
    x_values = [sp.simplify(sp.log(value) / sp.log(base)) for value in positive_t_values]
    x_values = [value for value in x_values if _is_valid_solution(problem.relation, variable, value)]
    solution_set = sp.FiniteSet(*x_values) if x_values else sp.EmptySet
    values = solution_values(solution_set)
    back_lines = [
        rf"{sp.latex(t)}={sp.latex(value)}\Rightarrow {sp.latex(base)}^{{{sp.latex(variable)}}}={sp.latex(value)}\Rightarrow {sp.latex(variable)}={sp.latex(sp.simplify(sp.log(value) / sp.log(base)))}"
        for value in positive_t_values
    ]
    substitution_equation_latex = rf"{sp.latex(t)}={sp.latex(base)}^{{{sp.latex(variable)}}},\quad {sp.latex(t)}>0"
    if denominator != 1:
        substitution_equation_latex += "\n" + rf"{sp.latex(denominator)}\ne0\quad\text{{đúng vì }}{sp.latex(t)}>0"
    return ExpLogTemplateResult(
        solution_set=solution_set,
        values=values,
        steps=[
            AlgebraSolveStep(
                index=start_index,
                title="Đặt ẩn phụ",
                explanation=f"Phương trình có các lũy thừa của {sp.sstr(base)}^x nên đặt t = {sp.sstr(base)}^x.",
                short_explanation=f"Đặt t = {sp.sstr(base)}^x, với t > 0.",
                detail_level="brief",
                method="exponential_substitution",
                goal="Đưa phương trình mũ về phương trình đại số theo t.",
                why="Các biểu thức như a^(2x), a^x hoặc a^(-x) đều viết được theo t = a^x.",
                rule="Đặt t = a^x",
                operation="Thay a^x bằng t, a^(-x) bằng 1/t, rồi khử mẫu nếu cần.",
                before_latex=sp.latex(relation),
                after_latex=substitution_equation_latex + "\n" + sp.latex(sp.Eq(poly.as_expr(), 0, evaluate=False)),
                pitfall="Không được quên t > 0 vì a^x luôn dương.",
                check="Thay t = a^x ngược lại phải ra phương trình ban đầu.",
                expression=sp.sstr(expression),
                expression_latex=sp.latex(expression),
                result=sp.sstr(poly.as_expr()),
                result_latex=sp.latex(sp.Eq(poly.as_expr(), 0, evaluate=False)),
                kind="transform",
                confidence="symbolic",
            ),
            AlgebraSolveStep(
                index=start_index + 1,
                title="Giải phương trình theo ẩn phụ",
                explanation="Giải phương trình đại số theo t rồi giữ các giá trị t dương.",
                short_explanation="Giải theo t và chỉ giữ t > 0.",
                detail_level="standard",
                method="solve_substitution_variable",
                goal="Tìm giá trị của a^x.",
                why="Sau khi đặt ẩn phụ, phương trình mũ đã trở thành phương trình đại số quen thuộc.",
                rule="Giải phương trình theo t",
                operation="Giải phương trình theo t và lọc điều kiện t > 0.",
                before_latex=sp.latex(sp.Eq(poly.as_expr(), 0, evaluate=False)),
                after_latex=_values_latex(t, positive_t_values),
                pitfall="Giá trị t không dương không thể bằng a^x.",
                check="Mỗi giá trị t giữ lại phải lớn hơn 0.",
                result="; ".join(sp.sstr(value) for value in positive_t_values),
                result_latex=_values_latex(t, positive_t_values),
                kind="solve",
                confidence="symbolic",
            ),
            AlgebraSolveStep(
                index=start_index + 2,
                title="Trả về biến ban đầu",
                explanation="Giải từng phương trình a^x = t để tìm x.",
                short_explanation="Đổi từ t về x bằng logarit.",
                detail_level="standard",
                method="back_substitute_exponential",
                goal="Tìm nghiệm theo biến ban đầu.",
                why="Bài toán hỏi x, nên không dừng ở nghiệm của t.",
                rule="Thay ngược ẩn phụ",
                operation="Giải a^x = t bằng x = log(t)/log(a).",
                before_latex=rf"{sp.latex(t)}={sp.latex(base)}^{{{sp.latex(variable)}}}",
                after_latex="\n".join(back_lines + [_values_latex(variable, values)]),
                pitfall="Nếu t không phải lũy thừa đẹp của cơ số, nghiệm được viết bằng log.",
                check="Thay nghiệm x vào phương trình ban đầu.",
                result="; ".join(sp.sstr(value) for value in values or []),
                result_latex=_values_latex(variable, values),
                kind="solve",
                confidence="symbolic",
            ),
        ],
    )


def _log_term(term: sp.Expr, variable: sp.Symbol) -> LogTerm | None:
    variable_logs = [item for item in term.atoms(sp.log) if item.args[0].has(variable)]
    if len(variable_logs) != 1:
        return None
    variable_log = variable_logs[0]
    ratio = sp.simplify(term / variable_log)
    constant_logs = [item for item in ratio.atoms(sp.log) if not item.args[0].has(variable)]
    if not constant_logs:
        if ratio.has(variable):
            return None
        return LogTerm(arg=variable_log.args[0], base=sp.E, coefficient=sp.simplify(ratio))
    if len(constant_logs) != 1:
        return None
    base_log = constant_logs[0]
    coefficient = sp.simplify(ratio * base_log)
    if coefficient.has(variable):
        return None
    return LogTerm(arg=variable_log.args[0], base=base_log.args[0], coefficient=coefficient)


def _log_method_title(log_terms: list[LogTerm], constant: sp.Expr) -> str:
    coefficients = [sp.simplify(item.coefficient) for item in log_terms]
    if len(log_terms) == 1 and coefficients[0] != 1:
        return "Đưa hệ số log vào biểu thức"
    if any(coef < 0 for coef in coefficients):
        return "Gộp log dạng thương"
    if len(log_terms) >= 2:
        return "Gộp log cùng cơ số"
    if constant != 0:
        return "Bỏ log"
    return "Biến đổi logarit"


def _as_power_with_base(expression: sp.Expr, variable: sp.Symbol) -> tuple[sp.Expr, sp.Expr] | None:
    if isinstance(expression, sp.Pow) and expression.exp.has(variable):
        return expression.base, expression.exp
    if expression.is_Integer and expression > 0:
        for base in range(2, 13):
            exponent = sp.log(expression, base)
            if exponent.is_integer:
                return sp.Integer(base), sp.Integer(exponent)
    return None


def _single_exponential_base(expression: sp.Expr, variable: sp.Symbol) -> sp.Expr | None:
    bases = sorted({
        power.base
        for power in expression.atoms(sp.Pow)
        if power.exp.has(variable) and not power.base.has(variable)
    }, key=sp.default_sort_key)
    if not bases:
        return None
    for candidate in bases:
        if all(_base_power_ratio(base, candidate) is not None for base in bases):
            return candidate
    return None


def _replace_base_power(expression: sp.Expr, variable: sp.Symbol, base: sp.Expr, t: sp.Symbol) -> sp.Expr | None:
    replaced = expression
    for power in sorted(expression.atoms(sp.Pow), key=lambda item: len(sp.sstr(item.exp)), reverse=True):
        if not power.exp.has(variable):
            continue
        ratio = _base_power_ratio(power.base, base)
        if ratio is None:
            continue
        coefficient = sp.simplify(ratio * power.exp / variable)
        if coefficient.has(variable) or not coefficient.is_integer:
            return None
        replaced = replaced.xreplace({power: t ** int(coefficient)})
    return sp.expand(replaced)


def _base_power_ratio(base: sp.Expr, candidate: sp.Expr) -> sp.Expr | None:
    if sp.simplify(base - candidate) == 0:
        return sp.Integer(1)
    try:
        ratio = sp.log(base, candidate)
        simplified = sp.simplify(ratio)
        if simplified.is_integer:
            return simplified
    except Exception:
        return None
    return None


def _solve_and_filter(expression: sp.Expr, problem: ParsedAlgebraProblem) -> sp.Set:
    variable = problem.variable
    domain = sp.S.Reals if problem.domain == "R" else sp.S.Complexes
    try:
        raw_set = sp.solveset(expression, variable, domain=domain)
    except Exception:
        try:
            raw_values = sp.solve(sp.Eq(expression, 0), variable)
            raw_set = sp.FiniteSet(*raw_values)
        except Exception:
            return sp.EmptySet
    values = solution_values(raw_set)
    if values is None:
        return raw_set
    valid = [sp.simplify(value) for value in values if problem.relation is not None and _is_valid_solution(problem.relation, variable, value)]
    return sp.FiniteSet(*valid) if valid else sp.EmptySet


def _is_valid_solution(relation: sp.Relational, variable: sp.Symbol, value: sp.Expr) -> bool:
    try:
        checked = sp.simplify(relation.subs(variable, value))
        if checked is sp.S.true:
            return True
        if checked is sp.S.false:
            return False
        return bool(checked)
    except Exception:
        return False


def _is_positive(value: sp.Expr) -> bool:
    try:
        checked = sp.simplify(value)
        if checked.is_positive is not None:
            return bool(checked.is_positive)
        return bool(checked > 0)
    except Exception:
        return False


def _values_latex(variable: sp.Symbol, values: list[sp.Expr] | None) -> str:
    if not values:
        return r"S=\varnothing"
    return r"S=\left\{" + ", ".join(sp.latex(value) for value in values) + r"\right\}"
