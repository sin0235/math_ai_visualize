from __future__ import annotations

from dataclasses import dataclass

import sympy as sp
from sympy.solvers.inequalities import solve_univariate_inequality

from app.schemas.algebra import AlgebraSolutionSet, AlgebraSolveResponse, AlgebraSolveStep
from app.services.algebra.domain import domain_assumptions_from_expression
from app.services.algebra.formatting import format_interval_set
from app.services.algebra.parser import ParsedAlgebraProblem
from app.services.algebra.steps import conclusion_step, domain_step, method_step
from app.services.algebra.transformations import detect_primary_technique
from app.services.algebra.verifier import verify_inequality_solution_set


def solve_inequality(problem: ParsedAlgebraProblem) -> AlgebraSolveResponse:
    if problem.relation is None or isinstance(problem.relation, sp.Equality):
        return _unsupported(problem, "Đầu vào không phải bất phương trình.")
    variable = problem.variable
    raw_expression = problem.relation.lhs - problem.relation.rhs
    expression = sp.simplify(raw_expression)
    assumptions = domain_assumptions_from_expression(raw_expression, variable)
    steps: list[AlgebraSolveStep] = []
    if assumptions:
        steps.append(domain_step(len(steps) + 1, assumptions))
    steps.append(method_step(len(steps) + 1, detect_primary_technique("inequality", expression, variable, problem.relation.rel_op)))
    try:
        result_set = solve_univariate_inequality(problem.relation, variable, relational=False)
    except Exception as exc:
        return _unsupported(problem, f"SymPy chưa giải được bất phương trình này: {exc}")
    relation_zero_latex = sp.latex(_relation_from_expression(expression, problem.relation.rel_op))
    steps.append(AlgebraSolveStep(
        index=len(steps) + 1,
        title="Đưa bất phương trình về một vế",
        explanation="Chuyển hết về một vế để xét dấu một biểu thức so với 0.",
        short_explanation="Chuyển hết về một vế để xét dấu.",
        detail_level="standard",
        method="sign_chart",
        goal="Tìm tập các giá trị làm bất phương trình đúng.",
        why="Khi một vế là 0, việc giải bất phương trình trở thành bài toán xét dấu.",
        rule="Chuyển vế",
        operation="Lấy vế trái trừ vế phải và giữ nguyên chiều bất phương trình.",
        before_latex=sp.latex(problem.relation),
        after_latex=relation_zero_latex,
        pitfall="Không được xử lý bất phương trình như phương trình; khi nhân chia với biểu thức có thể đổi dấu thì phải xét dấu.",
        check="Biểu thức một vế phải tương đương với bất phương trình ban đầu.",
        expression=sp.sstr(problem.relation),
        expression_latex=sp.latex(problem.relation),
        result=sp.sstr(expression),
        result_latex=relation_zero_latex,
        kind="transform",
        confidence="symbolic",
    ))
    sign_steps = _sign_chart_steps(expression, variable, problem.relation.rel_op, result_set, len(steps) + 1)
    steps.extend(sign_steps)
    result_set_for_verification = result_set if isinstance(result_set, sp.Set) else sp.S.UniversalSet
    verification = verify_inequality_solution_set(problem, result_set_for_verification, _verification_samples(expression, variable, result_set_for_verification))
    answer = format_interval_set(result_set)
    steps.append(_inequality_verification_step(len(steps) + 1, verification.status, result_set))
    steps.append(conclusion_step(len(steps) + 1, answer, sp.latex(result_set)))
    return AlgebraSolveResponse(
        input=problem.raw_input,
        normalized_input=problem.normalized_input,
        topic="inequality",
        problem_type="solve_inequality",
        status="solved" if verification.status in {"verified", "partially_verified"} else "partial",
        answer=answer,
        answer_latex=sp.latex(result_set),
        solution_set=AlgebraSolutionSet(kind="empty" if result_set is sp.EmptySet else "interval", text=answer, latex=sp.latex(result_set)),
        steps=steps,
        verification=verification,
        assumptions=assumptions,
        warnings=[] if sign_steps else ["Bất phương trình được kiểm chứng ở mức tập nghiệm symbolic; chưa tạo được bảng xét dấu chi tiết cho dạng này."],
        errors=[],
    )


def _domain_assumptions(relation: sp.Relational, variable: sp.Symbol) -> list[str]:
    expression = sp.simplify(relation.lhs - relation.rhs)
    assumptions: list[str] = []
    denominator = sp.denom(expression)
    if denominator != 1 and denominator.has(variable):
        assumptions.append(f"{sp.sstr(denominator)} khác 0")
    for log_expr in expression.atoms(sp.log):
        arg = log_expr.args[0]
        if arg.has(variable):
            assumptions.append(f"{sp.sstr(arg)} > 0")
    return assumptions


def _unsupported(problem: ParsedAlgebraProblem, message: str) -> AlgebraSolveResponse:
    return AlgebraSolveResponse(input=problem.raw_input, normalized_input=problem.normalized_input, topic="inequality", problem_type="solve_inequality", status="unsupported", answer=message, errors=[message])


@dataclass(frozen=True)
class SignInterval:
    start: sp.Expr
    end: sp.Expr
    sample: sp.Expr
    sign: str
    selected: bool


def _relation_from_expression(expression: sp.Expr, rel_op: str) -> sp.Relational:
    if rel_op == ">":
        return sp.Gt(expression, 0, evaluate=False)
    if rel_op == ">=":
        return sp.Ge(expression, 0, evaluate=False)
    if rel_op == "<":
        return sp.Lt(expression, 0, evaluate=False)
    return sp.Le(expression, 0, evaluate=False)


def _sign_chart_steps(expression: sp.Expr, variable: sp.Symbol, rel_op: str, result_set: sp.Set, start_index: int) -> list[AlgebraSolveStep]:
    numerator, denominator = sp.fraction(sp.together(sp.factor(expression)))
    zero_points = _real_roots(numerator, variable)
    excluded_points = _real_roots(denominator, variable) if denominator != 1 else []
    critical_points = sorted(set(zero_points + excluded_points), key=sp.default_sort_key)
    if not critical_points:
        return []

    factored = sp.factor(sp.together(expression))
    intervals = _sign_intervals(expression, variable, critical_points, result_set)
    if not intervals:
        return []

    critical_lines = [
        rf"{sp.latex(point)}:\quad {_critical_label(point, zero_points, excluded_points)}"
        for point in critical_points
    ]
    sign_lines = [
        rf"{_interval_latex(item.start, item.end)}:\quad f\left({sp.latex(item.sample)}\right)\ {item.sign}\ 0\quad\Rightarrow\quad {_selected_label(item.selected)}"
        for item in intervals
    ]
    return [
        AlgebraSolveStep(
            index=start_index,
            title="Phân tích dấu",
            explanation="Tìm các mốc làm biểu thức bằng 0 hoặc không xác định để chia trục số thành các khoảng.",
            goal="Xác định nơi dấu của biểu thức có thể thay đổi.",
            why="Với biểu thức hữu tỉ/đa thức, dấu chỉ đổi tại nghiệm của tử hoặc mốc làm mẫu bằng 0.",
            rule="Mốc xét dấu",
            operation="Phân tích tử và mẫu, rồi tìm các nghiệm thực liên quan.",
            before_latex=sp.latex(_relation_from_expression(expression, rel_op)),
            after_latex=sp.latex(factored) + "\n" + "\n".join(critical_lines),
            pitfall="Mốc làm mẫu bằng 0 chỉ dùng để chia khoảng, không được lấy làm nghiệm.",
            check="Các mốc tới hạn phải được sắp theo thứ tự trên trục số.",
            expression=sp.sstr(factored),
            expression_latex=sp.latex(factored),
            result="; ".join(sp.sstr(point) for point in critical_points),
            result_latex="\n".join(critical_lines),
            kind="transform",
            confidence="symbolic",
        ),
        AlgebraSolveStep(
            index=start_index + 1,
            title="Lập bảng xét dấu",
            explanation="Dấu trên từng khoảng được xác định bằng cách thử một giá trị đại diện trong khoảng đó.",
            goal="Chọn đúng các khoảng thỏa chiều bất phương trình.",
            why="Giữa hai mốc liên tiếp, dấu của biểu thức không đổi.",
            rule="Bảng xét dấu",
            operation="Chọn điểm thử trong mỗi khoảng và so sánh dấu với 0.",
            before_latex=sp.latex(factored),
            after_latex="\n".join(sign_lines),
            pitfall="Nếu bất phương trình có dấu bằng, chỉ lấy nghiệm của tử; không lấy mốc làm mẫu bằng 0.",
            check="Thay điểm thử trong mỗi khoảng vào biểu thức một vế để kiểm tra dấu.",
            expression=sp.sstr(factored),
            expression_latex=sp.latex(factored),
            result=sp.sstr(result_set),
            result_latex=sp.latex(result_set),
            kind="verify",
            confidence="symbolic",
        ),
        AlgebraSolveStep(
            index=start_index + 2,
            title="Chọn khoảng nghiệm",
            explanation="Ghép các khoảng có dấu phù hợp với bất phương trình và xử lý đúng điểm biên.",
            goal="Viết tập nghiệm cuối cùng từ bảng xét dấu.",
            why="Tập nghiệm của bất phương trình là hợp các khoảng làm quan hệ đúng.",
            rule="Chọn khoảng theo dấu",
            operation=f"Chọn các khoảng thỏa điều kiện f(x) {rel_op} 0.",
            before_latex="\n".join(sign_lines),
            after_latex=sp.latex(result_set),
            pitfall="Dấu ngoặc ở biên phụ thuộc vào dấu bằng và điều kiện xác định.",
            check="Mọi điểm trong khoảng chọn phải làm bất phương trình đúng; điểm ngoài phải làm sai.",
            result=sp.sstr(result_set),
            result_latex=sp.latex(result_set),
            kind="solve",
            confidence="symbolic",
        ),
    ]


def _real_roots(expression: sp.Expr, variable: sp.Symbol) -> list[sp.Expr]:
    try:
        roots = sp.solve(sp.Eq(expression, 0), variable)
    except Exception:
        return []
    return [sp.simplify(root) for root in roots if root.is_real is not False]


def _sign_intervals(expression: sp.Expr, variable: sp.Symbol, points: list[sp.Expr], result_set: sp.Set) -> list[SignInterval]:
    intervals: list[SignInterval] = []
    for index in range(len(points) + 1):
        start = -sp.oo if index == 0 else points[index - 1]
        end = sp.oo if index == len(points) else points[index]
        sample = _sample_between(start, end)
        sign = _sign_at(expression, variable, sample)
        if sign is None:
            continue
        selected = _point_in_set(sample, result_set)
        intervals.append(SignInterval(start=start, end=end, sample=sample, sign=sign, selected=selected))
    return intervals


def _verification_samples(expression: sp.Expr, variable: sp.Symbol, result_set: sp.Set) -> list[sp.Expr]:
    numerator, denominator = sp.fraction(sp.together(sp.factor(expression)))
    zero_points = _real_roots(numerator, variable)
    excluded_points = _real_roots(denominator, variable) if denominator != 1 else []
    critical_points = sorted(set(zero_points + excluded_points), key=sp.default_sort_key)
    samples = [item.sample for item in _sign_intervals(expression, variable, critical_points, result_set)]
    samples.extend(point for point in critical_points if _point_in_set(point, result_set))
    return samples


def _sample_between(start: sp.Expr, end: sp.Expr) -> sp.Expr:
    if start is -sp.oo:
        return end - 1
    if end is sp.oo:
        return start + 1
    return sp.simplify((start + end) / 2)


def _sign_at(expression: sp.Expr, variable: sp.Symbol, sample: sp.Expr) -> str | None:
    try:
        value = sp.simplify(expression.subs(variable, sample))
        if value.is_positive:
            return ">"
        if value.is_negative:
            return "<"
        if value.is_zero:
            return "="
    except Exception:
        return None
    return None


def _point_in_set(point: sp.Expr, result_set: sp.Set) -> bool:
    try:
        return bool(result_set.contains(point))
    except Exception:
        return False


def _critical_label(point: sp.Expr, zero_points: list[sp.Expr], excluded_points: list[sp.Expr]) -> str:
    is_zero = any(sp.simplify(point - root) == 0 for root in zero_points)
    is_excluded = any(sp.simplify(point - root) == 0 for root in excluded_points)
    if is_zero and is_excluded:
        return r"\text{tử bằng 0 nhưng mẫu cũng bằng 0, loại}"
    if is_excluded:
        return r"\text{mẫu bằng 0, loại}"
    return r"\text{tử bằng 0}"


def _selected_label(selected: bool) -> str:
    return r"\text{chọn}" if selected else r"\text{không chọn}"


def _interval_latex(start: sp.Expr, end: sp.Expr) -> str:
    return rf"\left({_bound_latex(start)};\,{_bound_latex(end)}\right)"


def _bound_latex(value: sp.Expr) -> str:
    if value is sp.oo:
        return r"+\infty"
    if value is -sp.oo:
        return r"-\infty"
    return sp.latex(value)


def _inequality_verification_step(index: int, status: str, result_set: sp.Set) -> AlgebraSolveStep:
    confidence = "verified" if status == "verified" else "symbolic" if status == "partially_verified" else "unverified"
    return AlgebraSolveStep(
        index=index,
        title="Kiểm tra tập nghiệm",
        explanation="Đối chiếu tập nghiệm symbolic với bất phương trình ban đầu.",
        goal="Xác nhận các khoảng nghiệm không bị chọn nhầm dấu hoặc sai biên.",
        why="Với bất phương trình, lỗi thường gặp là lấy nhầm khoảng hoặc quên loại điểm không xác định.",
        rule="Kiểm chứng tập nghiệm",
        operation="Dùng biểu diễn tập nghiệm để kiểm tra quan hệ và các biên khoảng.",
        after_latex=sp.latex(result_set),
        pitfall="Dấu ngoặc tròn/vuông ở biên khoảng phụ thuộc vào dấu <, <=, >, >= và điều kiện xác định.",
        check="Thử một điểm trong mỗi khoảng được chọn và một điểm ngoài tập nghiệm để so sánh.",
        result=sp.sstr(result_set),
        result_latex=sp.latex(result_set),
        kind="verify",
        confidence=confidence,
    )
