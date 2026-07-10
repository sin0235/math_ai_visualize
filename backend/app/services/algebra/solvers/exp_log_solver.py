from __future__ import annotations

import sympy as sp

from app.schemas.algebra import AlgebraSolutionSet, AlgebraSolutionValue, AlgebraSolveResponse, AlgebraSolveStep
from app.services.algebra.domain import domain_assumptions_from_expression
from app.services.algebra.exp_log_transformations import solve_exp_log_template
from app.services.algebra.formatting import format_solution_set, solution_values
from app.services.algebra.parser import ParsedAlgebraProblem
from app.services.algebra.steps import conclusion_step, domain_step
from app.services.algebra.verifier import verify_finite_solutions, verify_solution_set


def solve_exp_log(problem: ParsedAlgebraProblem) -> AlgebraSolveResponse:
    if problem.relation is None or not isinstance(problem.relation, sp.Equality):
        return _unsupported(problem, "Đầu vào không phải phương trình mũ-log.")
    variable = problem.variable
    raw_expression = problem.relation.lhs - problem.relation.rhs
    # simplify() can rewrite exp(x)+exp(-x) → cosh(x) and hide the exp structure used by templates.
    simplified = sp.simplify(raw_expression)
    if not _is_exp_log_expression(raw_expression) and not _is_exp_log_expression(simplified):
        return _unsupported(problem, "Phương trình không chứa thành phần mũ hoặc log.")
    # Prefer a form that still exposes exp/log/power atoms for pedagogy templates.
    if _has_exp_log_atoms(raw_expression) and not _has_exp_log_atoms(simplified):
        expression = raw_expression
    elif _has_exp_log_atoms(simplified):
        expression = simplified
    else:
        expression = raw_expression if _is_exp_log_expression(raw_expression) else simplified
    assumptions = domain_assumptions_from_expression(raw_expression, variable)
    
    milestones: list[str] = []
    if problem.relation is not None:
        milestones.append(f"Phương trình gốc: {sp.latex(problem.relation)}")
        
    steps: list[AlgebraSolveStep] = []
    if assumptions:
        steps.append(domain_step(len(steps) + 1, assumptions))
    template_result = solve_exp_log_template(problem, len(steps) + 1)
    if template_result is not None:
        solution_set = template_result.solution_set
        values = template_result.values
        steps.extend(template_result.steps)
    else:
        try:
            domain = sp.S.Reals if problem.domain == "R" else sp.S.Complexes
            solution_set = sp.solveset(expression, variable, domain=domain)
            if isinstance(solution_set, sp.ConditionSet) and expression is not simplified:
                # Retry with simplified form when raw keeps ConditionSet.
                alt = sp.solveset(simplified, variable, domain=domain)
                if not isinstance(alt, sp.ConditionSet):
                    solution_set = alt
            if isinstance(solution_set, sp.ConditionSet):
                return _unsupported(
                    problem,
                    "Phương trình mũ-log này chưa được rút gọn thành tập nghiệm tường minh (ConditionSet).",
                )
        except Exception as exc:
            return _unsupported(problem, f"SymPy chưa giải được phương trình mũ-log này: {exc}")
        values = solution_values(solution_set)
        if values is not None:
            values = [value for value in values if _is_valid_solution(problem.relation, variable, value)]
            solution_set = sp.FiniteSet(*values) if values else sp.EmptySet
        method_steps = _exp_log_method_steps(problem, expression, variable, values, len(steps) + 1)
        if method_steps:
            steps.extend(method_steps)
        else:
            steps.append(AlgebraSolveStep(
                index=len(steps) + 1,
                title="Giải phương trình còn lại",
                explanation="Giải phương trình sau khi đã biến đổi log/mũ và giữ điều kiện xác định.",
                short_explanation="Giải phần còn lại rồi thử lại với đề gốc.",
                detail_level="standard",
                method="symbolic_exp_log_solve",
                goal="Tìm nghiệm ứng viên của phương trình.",
                why="Sau các phép biến đổi mũ-log, bài toán thường trở về phương trình đại số quen thuộc.",
                rule="Giải phương trình mũ-log",
                operation="Giải phương trình trên miền nghiệm đã chọn rồi thử lại điều kiện.",
                expression=sp.sstr(expression),
                expression_latex=sp.latex(expression),
                result=sp.sstr(solution_set),
                result_latex=sp.latex(solution_set),
                kind="solve",
                confidence="symbolic",
            ))
    interval_note = None
    if problem.solve_interval is not None:
        try:
            solution_set = solution_set.intersect(problem.solve_interval)
            values = solution_values(solution_set)
            interval_note = f"Nghiệm đã được lọc theo khoảng người dùng chọn: {sp.latex(problem.solve_interval)}."
            assumptions = assumptions + [f"Khoảng nghiệm: {sp.latex(problem.solve_interval)}"]
        except Exception:
            interval_note = "Không áp dụng được khoảng nghiệm đã chọn; giữ tập nghiệm trên miền gốc."
    answer = format_solution_set(solution_set)
    solution = AlgebraSolutionSet(
        kind="empty" if solution_set is sp.EmptySet else "finite" if values is not None else "set",
        text=answer,
        latex=sp.latex(solution_set),
        values=[AlgebraSolutionValue(text=sp.sstr(value), latex=sp.latex(value), approximate=str(sp.N(value, 8))) for value in values or []],
    )
    verification = verify_finite_solutions(problem, values) if values is not None else verify_solution_set(problem, solution_set)
    status = "solved" if verification.status in {"verified", "partially_verified"} else "error"
    steps.append(conclusion_step(len(steps) + 1, answer, sp.latex(solution_set)))
    if values is not None and len(values) > 0:
        roots_latex = ", ".join(sp.latex(sp.Eq(variable, val, evaluate=False)) for val in values)
        milestones.append(f"Tập nghiệm: {roots_latex}")
    else:
        milestones.append(f"Tập nghiệm: {sp.latex(solution_set)}")
        
    return AlgebraSolveResponse(
        input=problem.raw_input,
        normalized_input=problem.normalized_input,
        topic="exponential_log",
        problem_type="solve_exp_log_equation",
        status=status,
        answer=answer,
        answer_latex=sp.latex(solution_set),
        solution_set=solution,
        steps=steps,
        milestones=milestones,
        verification=verification,
        assumptions=assumptions,
        warnings=[
            *([] if values is not None else ["Tập nghiệm mũ-log symbolic không hữu hạn nên chỉ kiểm chứng ở mức biểu diễn tập nghiệm."]),
            *([interval_note] if interval_note else []),
        ],
        errors=[] if status == "solved" else ["Kiểm chứng nghiệm mũ-log thất bại."],
    )


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


def _exp_log_method_steps(problem: ParsedAlgebraProblem, expression: sp.Expr, variable: sp.Symbol, values: list[sp.Expr] | None, start_index: int) -> list[AlgebraSolveStep]:
    return (
        _log_sum_steps(problem, variable, values, start_index)
        or _log_transform_steps(problem, start_index)
        or _same_base_exp_steps(problem, variable, values, start_index)
        or _exp_substitution_steps(problem, expression, variable, values, start_index)
    )


def _log_transform_steps(problem: ParsedAlgebraProblem, start_index: int) -> list[AlgebraSolveStep]:
    if problem.relation is None:
        return []
    lhs = problem.relation.lhs
    rhs = problem.relation.rhs
    numerator, denominator = lhs.as_numer_denom()
    if numerator.func is sp.log and denominator.func is sp.log and not rhs.has(problem.variable):
        arg = numerator.args[0]
        base = denominator.args[0]
        target = sp.Pow(base, rhs, evaluate=False)
        return [AlgebraSolveStep(
            index=start_index,
            title="Bỏ log",
            explanation=f"Dùng định nghĩa log: log cơ số {sp.sstr(base)} của A bằng {sp.sstr(rhs)} thì A = {sp.sstr(base)}^{sp.sstr(rhs)}.",
            goal="Đưa phương trình log về phương trình đại số.",
            why="Theo định nghĩa logarit, log_b(A)=c tương đương A=b^c với điều kiện A>0, b>0, b khác 1.",
            rule="Định nghĩa logarit",
            operation="Giữ điều kiện xác định rồi chuyển log sang dạng lũy thừa.",
            before_latex=sp.latex(problem.relation),
            after_latex=sp.latex(sp.Eq(arg, target, evaluate=False)),
            pitfall="Không được bỏ qua điều kiện của biểu thức trong log.",
            check="Nghiệm sau khi giải phải thay lại vào log ban đầu.",
            expression=sp.sstr(arg),
            expression_latex=sp.latex(arg),
            result=sp.sstr(target),
            result_latex=sp.latex(sp.Eq(arg, target, evaluate=False)),
            kind="transform",
            confidence="symbolic",
        )]
    return []


def _log_sum_steps(problem: ParsedAlgebraProblem, variable: sp.Symbol, values: list[sp.Expr] | None, start_index: int) -> list[AlgebraSolveStep]:
    if problem.relation is None:
        return []
    lhs = problem.relation.lhs
    rhs = problem.relation.rhs
    if rhs.has(variable):
        return []
    terms = sp.Add.make_args(lhs)
    if len(terms) < 2:
        return []
    parsed = [_log_base_term(term, variable) for term in terms]
    if any(item is None for item in parsed):
        return []
    base = parsed[0][1]  # type: ignore[index]
    if any(sp.simplify(item[1] - base) != 0 for item in parsed if item is not None):
        return []
    args = [item[0] for item in parsed if item is not None]
    combined_arg = sp.factor(sp.prod(args))
    target = sp.Pow(base, rhs, evaluate=False)
    candidate_latex = _values_latex(problem.variable, values)
    return [
        AlgebraSolveStep(
            index=start_index,
            title="Gộp log cùng cơ số",
            explanation="Các log cùng cơ số đang cộng với nhau nên gộp thành log của tích.",
            goal="Đưa nhiều log về một log duy nhất.",
            why="Với các biểu thức dương, log_a M + log_a N = log_a(MN).",
            rule="Tính chất cộng logarit",
            operation="Nhân các biểu thức trong log lại với nhau.",
            before_latex=sp.latex(problem.relation),
            after_latex=sp.latex(sp.Eq(sp.log(combined_arg) / sp.log(base), rhs, evaluate=False)),
            pitfall="Chỉ gộp được khi các log cùng cơ số và các biểu thức trong log đều dương.",
            check="Điều kiện xác định phải chứa từng biểu thức trong log lớn hơn 0.",
            expression=sp.sstr(lhs),
            expression_latex=sp.latex(lhs),
            result=sp.sstr(combined_arg),
            result_latex=sp.latex(combined_arg),
            kind="transform",
            confidence="symbolic",
        ),
        AlgebraSolveStep(
            index=start_index + 1,
            title="Bỏ log",
            explanation="Dùng định nghĩa log để chuyển phương trình log về phương trình đại số.",
            goal="Tìm phương trình không còn log.",
            why="log_a(A)=c tương đương A=a^c khi điều kiện log thỏa mãn.",
            rule="Định nghĩa logarit",
            operation="Cho biểu thức trong log bằng lũy thừa của cơ số.",
            before_latex=sp.latex(sp.Eq(sp.log(combined_arg) / sp.log(base), rhs, evaluate=False)),
            after_latex=sp.latex(sp.Eq(combined_arg, target, evaluate=False)),
            pitfall="Bước này chỉ cho nghiệm ứng viên; vẫn phải thử lại điều kiện log.",
            check="Thay nghiệm vào từng log ban đầu để kiểm tra.",
            expression=sp.sstr(combined_arg),
            expression_latex=sp.latex(combined_arg),
            result=sp.sstr(target),
            result_latex=sp.latex(sp.Eq(combined_arg, target, evaluate=False)),
            kind="transform",
            confidence="symbolic",
        ),
        AlgebraSolveStep(
            index=start_index + 2,
            title="Thử lại điều kiện log",
            explanation="Giữ những nghiệm làm tất cả biểu thức trong log dương và thỏa phương trình ban đầu.",
            goal="Loại nghiệm không hợp lệ do điều kiện log.",
            why="Logarit chỉ xác định khi biểu thức bên trong lớn hơn 0.",
            rule="Thay lại nghiệm",
            operation="Thay từng nghiệm ứng viên vào phương trình ban đầu.",
            before_latex=sp.latex(problem.relation),
            after_latex=candidate_latex,
            pitfall="Không được chỉ giải phương trình sau khi bỏ log rồi kết luận.",
            check="Mọi nghiệm cuối cùng phải làm từng log có nghĩa.",
            result="; ".join(sp.sstr(value) for value in values or []),
            result_latex=candidate_latex,
            kind="verify",
            confidence="verified",
        ),
    ]


def _same_base_exp_steps(problem: ParsedAlgebraProblem, variable: sp.Symbol, values: list[sp.Expr] | None, start_index: int) -> list[AlgebraSolveStep]:
    if problem.relation is None:
        return []
    left = _as_power_with_base(problem.relation.lhs, variable)
    right = _as_power_with_base(problem.relation.rhs, variable)
    if left is None or right is None:
        return []
    base_left, exp_left = left
    base_right, exp_right = right
    if sp.simplify(base_left - base_right) != 0:
        return []
    return [
        AlgebraSolveStep(
            index=start_index,
            title="Đưa về cùng cơ số",
            explanation="Hai vế là lũy thừa cùng cơ số dương khác 1 nên so sánh số mũ.",
            goal="Biến phương trình mũ thành phương trình theo số mũ.",
            why="Nếu a > 0, a khác 1 và a^u = a^v thì u = v.",
            rule="Cùng cơ số",
            operation="Viết hai vế dưới dạng cùng cơ số rồi cho hai số mũ bằng nhau.",
            before_latex=sp.latex(problem.relation),
            after_latex=sp.latex(sp.Eq(exp_left, exp_right, evaluate=False)),
            pitfall="Không dùng quy tắc này nếu cơ số không cùng nhau hoặc cơ số không hợp lệ.",
            check="Lũy thừa sau khi đổi cơ số phải đúng với hai vế ban đầu.",
            expression=sp.sstr(problem.relation),
            expression_latex=sp.latex(problem.relation),
            result=sp.sstr(sp.Eq(exp_left, exp_right, evaluate=False)),
            result_latex=sp.latex(sp.Eq(exp_left, exp_right, evaluate=False)),
            kind="transform",
            confidence="symbolic",
        ),
        AlgebraSolveStep(
            index=start_index + 1,
            title="Giải phương trình số mũ",
            explanation="Giải phương trình thu được từ việc so sánh hai số mũ.",
            goal="Tìm nghiệm của biến.",
            why="Sau khi cùng cơ số, bài toán trở thành phương trình đại số đơn giản hơn.",
            rule="Giải phương trình đại số",
            operation="Giải phương trình giữa hai số mũ.",
            before_latex=sp.latex(sp.Eq(exp_left, exp_right, evaluate=False)),
            after_latex=_values_latex(problem.variable, values),
            pitfall="Nếu có điều kiện miền nghiệm, vẫn phải kiểm tra lại.",
            check="Thay nghiệm vào phương trình mũ ban đầu.",
            result="; ".join(sp.sstr(value) for value in values or []),
            result_latex=_values_latex(problem.variable, values),
            kind="solve",
            confidence="symbolic",
        ),
    ]


def _exp_substitution_steps(problem: ParsedAlgebraProblem, expression: sp.Expr, variable: sp.Symbol, values: list[sp.Expr] | None, start_index: int) -> list[AlgebraSolveStep]:
    base = _single_exponential_base(expression, variable)
    if base is None:
        return []
    t = sp.Symbol("t", positive=True)
    rewritten = _replace_base_power(expression, variable, base, t)
    if rewritten is None:
        return []
    try:
        poly = sp.Poly(sp.expand(rewritten), t)
    except sp.PolynomialError:
        return []
    if poly.degree() < 2:
        return []
    t_values = solution_values(sp.solveset(poly.as_expr(), t, domain=sp.S.Reals)) or []
    positive_t_values = [value for value in t_values if sp.simplify(value).is_positive is not False]
    back_lines = [rf"{sp.latex(t)}={sp.latex(value)}\Rightarrow {sp.latex(base)}^{sp.latex(variable)}={sp.latex(value)}" for value in positive_t_values]
    return [
        AlgebraSolveStep(
            index=start_index,
            title="Đặt ẩn phụ",
            explanation=f"Phương trình có các lũy thừa của {sp.sstr(base)}^x nên đặt t = {sp.sstr(base)}^x.",
            goal="Đưa phương trình mũ về phương trình đại số theo t.",
            why="Các biểu thức như a^(2x) có thể viết thành (a^x)^2.",
            rule="Đặt t = a^x",
            operation="Thay a^x bằng t và nhớ t > 0.",
            before_latex=sp.latex(problem.relation) if problem.relation is not None else sp.latex(expression),
            after_latex=rf"{sp.latex(t)}={sp.latex(base)}^{sp.latex(variable)},\quad {sp.latex(t)}>0" + "\n" + sp.latex(sp.Eq(poly.as_expr(), 0, evaluate=False)),
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
            goal="Tìm nghiệm theo biến ban đầu.",
            why="Bài toán hỏi x, nên không dừng ở nghiệm của t.",
            rule="Thay ngược ẩn phụ",
            operation="Giải các phương trình mũ đơn giản thu được.",
            before_latex=rf"{sp.latex(t)}={sp.latex(base)}^{sp.latex(variable)}",
            after_latex="\n".join(back_lines + [_values_latex(variable, values)]),
            pitfall="Nếu t không phải lũy thừa đẹp của cơ số, nghiệm có thể viết bằng log.",
            check="Thay nghiệm x vào phương trình ban đầu.",
            result="; ".join(sp.sstr(value) for value in values or []),
            result_latex=_values_latex(variable, values),
            kind="solve",
            confidence="symbolic",
        ),
    ]


def _log_base_term(term: sp.Expr, variable: sp.Symbol) -> tuple[sp.Expr, sp.Expr] | None:
    numerator, denominator = term.as_numer_denom()
    if numerator.func is not sp.log or denominator.func is not sp.log:
        return None
    arg = numerator.args[0]
    base = denominator.args[0]
    if base.has(variable):
        return None
    return arg, base


def _as_power_with_base(expression: sp.Expr, variable: sp.Symbol) -> tuple[sp.Expr, sp.Expr] | None:
    if expression.func is sp.exp and expression.args[0].has(variable):
        return sp.E, expression.args[0]
    if isinstance(expression, sp.Pow) and expression.exp.has(variable):
        return expression.base, expression.exp
    if expression.is_Integer and expression > 0:
        for base in range(2, 11):
            exponent = sp.log(expression, base)
            if exponent.is_integer:
                return sp.Integer(base), sp.Integer(exponent)
    return None


def _true_exp_nodes(expression: sp.Expr) -> list[sp.Expr]:
    return [
        node
        for node in sp.preorder_traversal(expression)
        if getattr(node, "func", None) is sp.exp and len(getattr(node, "args", ())) == 1
    ]


def _single_exponential_base(expression: sp.Expr, variable: sp.Symbol) -> sp.Expr | None:
    bases: set[sp.Expr] = set()
    for power in expression.atoms(sp.Pow):
        if power.exp.has(variable) and not power.base.has(variable):
            bases.add(power.base)
    if _true_exp_nodes(expression):
        bases.add(sp.E)
    if not bases:
        return None
    ordered = sorted(bases, key=sp.default_sort_key)
    for candidate in ordered:
        if all(_base_power_ratio(base, candidate) is not None for base in ordered):
            return candidate
    return None


def _replace_base_power(expression: sp.Expr, variable: sp.Symbol, base: sp.Expr, t: sp.Symbol) -> sp.Expr | None:
    replaced = expression
    if _base_power_ratio(sp.E, base) is not None or sp.simplify(base - sp.E) == 0:
        def _exp_to_t(node: sp.Expr) -> sp.Expr:
            coeff = sp.simplify(node.args[0] / variable)
            if coeff.has(variable) or not coeff.is_integer:
                return node
            return t ** int(coeff)

        replaced = replaced.replace(
            lambda node: getattr(node, "func", None) is sp.exp
            and len(getattr(node, "args", ())) == 1
            and node.args[0].has(variable),
            _exp_to_t,
        )
    for power in sorted(replaced.atoms(sp.Pow), key=lambda item: len(sp.sstr(item.exp)), reverse=True):
        if not power.exp.has(variable):
            continue
        ratio = _base_power_ratio(power.base, base)
        if ratio is None:
            continue
        coefficient = sp.simplify(ratio * power.exp / variable)
        if coefficient.has(variable) or not coefficient.is_integer:
            return None
        replaced = replaced.replace(power, t ** int(coefficient))
    if replaced.has(variable) and (
        _true_exp_nodes(replaced)
        or any(isinstance(p, sp.Pow) and p.exp.has(variable) for p in replaced.atoms(sp.Pow))
    ):
        return None
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


def _values_latex(variable: sp.Symbol, values: list[sp.Expr] | None) -> str:
    if not values:
        return r"S=\varnothing"
    return r"S=\left\{" + ", ".join(sp.latex(value) for value in values) + r"\right\}"


def _is_exp_log_expression(expression: sp.Expr) -> bool:
    if _has_exp_log_atoms(expression):
        return True
    # After simplify, exp±exp may become cosh/sinh; still treat as exp-log family.
    return expression.has(sp.cosh, sp.sinh, sp.tanh)


def _has_exp_log_atoms(expression: sp.Expr) -> bool:
    return (
        expression.has(sp.log)
        or expression.has(sp.exp)
        or any(
            isinstance(power, sp.Pow) and power.exp.has(*expression.free_symbols)
            for power in expression.atoms(sp.Pow)
        )
    )


def _unsupported(problem: ParsedAlgebraProblem, message: str) -> AlgebraSolveResponse:
    return AlgebraSolveResponse(input=problem.raw_input, normalized_input=problem.normalized_input, topic="exponential_log", problem_type="solve_exp_log_equation", status="unsupported", answer=message, errors=[message])
