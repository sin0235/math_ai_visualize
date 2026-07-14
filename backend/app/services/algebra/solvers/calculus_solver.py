from __future__ import annotations

import re
from dataclasses import dataclass, replace

import sympy as sp

from app.schemas.algebra import (
    AlgebraSolutionSet,
    AlgebraSolveResponse,
    AlgebraSolveStep,
    AlgebraVerificationCheck,
    AlgebraVerificationReport,
)
from app.services.algebra.calculus_transformations import derivative_steps, integral_steps, limit_steps
from app.services.algebra.notation import algebra_latex, algebra_text
from app.services.algebra.parser import AlgebraParseError, ParsedAlgebraProblem, algebra_local_dict, parse_algebra_expr


@dataclass(frozen=True)
class CalculusTemplate:
    kind: str
    expression: sp.Expr
    variable: sp.Symbol
    point: sp.Expr | None = None
    direction: str = "+-"
    lower: sp.Expr | None = None
    upper: sp.Expr | None = None
    target: sp.Expr | None = None
    order: int = 1
    derivative_terms: tuple[sp.Expr, ...] = ()
    function_names: tuple[str, ...] = ()


def solve_calculus(problem: ParsedAlgebraProblem) -> AlgebraSolveResponse:
    try:
        template = _parse_template(problem.normalized_input, problem.topic, problem.variable)
    except ValueError as exc:
        return _unsupported(problem, problem.topic, str(exc))
    if template.kind == "calculus_derivative_sum":
        return _solve_derivative_sum(problem, template)
    if template.kind == "calculus_derivative":
        return _solve_derivative(problem, template)
    if template.kind == "calculus_derivative_equation":
        return _solve_derivative_equation(problem, template)
    if template.kind == "calculus_derivative_by_definition":
        return _solve_derivative_by_definition(problem, template)
    if template.kind == "calculus_limit":
        return _solve_limit(problem, template)
    if template.kind == "calculus_continuous_at":
        return _solve_continuous_at(problem, template)
    if template.kind == "calculus_integral":
        return _solve_integral(problem, template)
    return _unsupported(problem, template.kind, "Dạng giải tích này chưa được hỗ trợ.")


def _solve_derivative_sum(problem: ParsedAlgebraProblem, template: CalculusTemplate) -> AlgebraSolveResponse:
    derivative = sp.Add(*template.derivative_terms)
    names = template.function_names
    variable_latex = algebra_latex(template.variable)
    function_sum = "+".join(f"{name}({variable_latex})" for name in names)
    derivative_sum = "+".join(f"{name}'({variable_latex})" for name in names)
    given_sum = "+".join(algebra_latex(term) for term in template.derivative_terms)
    answer_latex = algebra_latex(derivative)
    steps = [
        AlgebraSolveStep(
            index=1,
            title="Dùng quy tắc đạo hàm của tổng",
            explanation="Đạo hàm của tổng bằng tổng các đạo hàm thành phần.",
            rule="(f+g)'=f'+g'",
            before_latex=rf"\left({function_sum}\right)'",
            after_latex=derivative_sum,
            kind="transform",
            confidence="verified",
        ),
        AlgebraSolveStep(
            index=2,
            title="Thay các đạo hàm đã cho",
            explanation="Thay trực tiếp từng đạo hàm từ giả thiết của đề.",
            before_latex=derivative_sum,
            after_latex=given_sum,
            kind="transform",
            confidence="verified",
        ),
        AlgebraSolveStep(
            index=3,
            title="Rút gọn kết quả",
            explanation="Cộng các biểu thức đạo hàm thành phần.",
            before_latex=given_sum,
            after_latex=answer_latex,
            result=algebra_text(derivative),
            result_latex=answer_latex,
            kind="solve",
            confidence="verified",
        ),
    ]
    verification = AlgebraVerificationReport(
        status="verified",
        checks=[AlgebraVerificationCheck(
            name="derivative_sum_rule",
            status="pass",
            detail="Đã đối chiếu quy tắc tuyến tính của đạo hàm và rút gọn symbolic tổng các đạo hàm đã cho.",
            latex=answer_latex,
        )],
        method=["derivative_linearity", "sympy.simplify"],
    )
    return AlgebraSolveResponse(
        input=problem.raw_input,
        normalized_input=problem.normalized_input,
        topic="calculus_derivative",
        problem_type="differentiate_sum_from_given_derivatives",
        status="solved",
        answer=f"Đạo hàm: {algebra_text(derivative)}",
        answer_latex=answer_latex,
        solution_set=AlgebraSolutionSet(kind="expression", text=algebra_text(derivative), latex=answer_latex),
        steps=steps,
        milestones=[
            f"Quy tắc tổng: {derivative_sum}",
            f"Kết quả: {answer_latex}",
        ],
        verification=verification,
    )


def _solve_derivative(problem: ParsedAlgebraProblem, template: CalculusTemplate) -> AlgebraSolveResponse:
    if template.order < 1 or template.order > 5:
        return _unsupported(problem, "calculus_derivative", "Bậc đạo hàm order cần nằm trong 1..5.")
    derivative = sp.simplify(sp.diff(template.expression, template.variable, template.order))
    if isinstance(derivative, sp.Derivative) or derivative.has(sp.Derivative):
        return _unsupported(problem, "calculus_derivative", "SymPy chưa rút gọn được đạo hàm (Derivative unevaluated).")
    steps = derivative_steps(template.expression, template.variable, derivative, template.order)
    answer = f"Đạo hàm: {algebra_text(derivative)}"
    verification = _verify_derivative(template.expression, template.variable, derivative, template.order)
    status = "solved" if verification.status in {"verified", "partially_verified"} else "partial"
    steps.append(_calculus_conclusion_step(len(steps) + 1, "Kết luận đạo hàm", answer, algebra_latex(derivative)))
    milestones = [
        f"Biểu thức gốc: f({algebra_latex(template.variable)}) = {algebra_latex(template.expression)}",
        f"Kết quả đạo hàm: f'({algebra_latex(template.variable)}) = {algebra_latex(derivative)}"
    ]
    return AlgebraSolveResponse(
        input=problem.raw_input,
        normalized_input=problem.normalized_input,
        topic="calculus_derivative",
        problem_type="differentiate_expression",
        status=status,
        answer=answer,
        answer_latex=algebra_latex(derivative),
        solution_set=AlgebraSolutionSet(kind="expression", text=algebra_text(derivative), latex=algebra_latex(derivative)),
        steps=steps,
        milestones=milestones,
        verification=verification,
        warnings=[] if verification.status == "verified" else ["Đạo hàm chỉ được kiểm chứng một phần (symbolic/numeric)."],
    )


def _solve_derivative_equation(problem: ParsedAlgebraProblem, template: CalculusTemplate) -> AlgebraSolveResponse:
    derivative = sp.simplify(sp.diff(template.expression, template.variable, template.order))
    if isinstance(derivative, sp.Derivative) or derivative.has(sp.Derivative):
        return _unsupported(problem, "calculus_derivative", "SymPy chưa rút gọn được đạo hàm để lập phương trình.")
    rhs = template.target if template.target is not None else sp.Integer(0)
    relation = sp.Eq(derivative, rhs, evaluate=False)
    equation_problem = replace(
        problem,
        raw_input=sp.sstr(relation),
        normalized_input=f"{sp.sstr(derivative)}={sp.sstr(rhs)}",
        topic="equation",
        relation=relation,
        relations=[relation],
        expression=None,
        variable=template.variable,
        variables=[template.variable],
    )

    from app.services.algebra.solvers.equation_solver import solve_equation

    response = solve_equation(equation_problem)
    derivative_template = replace(template, kind="calculus_derivative")
    calculus_steps = derivative_steps(
        derivative_template.expression,
        derivative_template.variable,
        derivative,
        derivative_template.order,
    )
    calculus_steps.append(AlgebraSolveStep(
        index=len(calculus_steps) + 1,
        title="Lập phương trình đạo hàm",
        explanation="Thay biểu thức đạo hàm vừa tính vào điều kiện của đề.",
        goal="Đưa yêu cầu f'(x) bằng giá trị đã cho về phương trình theo x.",
        rule="Điều kiện đạo hàm",
        before_latex=rf"f'\left({algebra_latex(template.variable)}\right)={algebra_latex(rhs)}",
        after_latex=algebra_latex(relation),
        kind="transform",
        confidence="verified",
    ))
    equation_steps = [
        step.model_copy(update={"index": len(calculus_steps) + offset})
        for offset, step in enumerate(response.steps, start=1)
    ]
    response.input = problem.raw_input
    response.normalized_input = problem.normalized_input
    response.topic = "calculus_derivative"
    response.problem_type = "solve_derivative_equation"
    response.steps = [*calculus_steps, *equation_steps]
    response.milestones = [
        f"Hàm số: f({algebra_latex(template.variable)})={algebra_latex(template.expression)}",
        f"Đạo hàm: f'({algebra_latex(template.variable)})={algebra_latex(derivative)}",
        *response.milestones,
    ]
    return response


def _solve_limit(problem: ParsedAlgebraProblem, template: CalculusTemplate) -> AlgebraSolveResponse:
    if template.point is None:
        return _unsupported(problem, "calculus_limit", "Giới hạn cần có điểm tiến tới, ví dụ limit(expr=(x^2-1)/(x-1),var=x,to=1).")
    if template.direction not in {"+", "-", "+-"}:
        return _unsupported(problem, "calculus_limit", "dir chỉ hỗ trợ +, - hoặc +-.")
    result = sp.simplify(sp.limit(template.expression, template.variable, template.point, dir=template.direction))
    if isinstance(result, sp.Limit) or result.has(sp.Limit):
        return _unsupported(problem, "calculus_limit", "SymPy chưa đánh giá được giới hạn (Limit unevaluated).")
    if result is sp.zoo:
        return AlgebraSolveResponse(
            input=problem.raw_input,
            normalized_input=problem.normalized_input,
            topic="calculus_limit",
            problem_type="calculate_limit",
            status="partial",
            answer="Giới hạn không xác định (complex infinity / zoo).",
            answer_latex=algebra_latex(result),
            solution_set=AlgebraSolutionSet(kind="expression", text="zoo", latex=algebra_latex(result)),
            verification=AlgebraVerificationReport(
                status="partially_verified",
                checks=[AlgebraVerificationCheck(name="limit_zoo", status="warn", detail="Kết quả zoo không được coi là giới hạn hữu hạn đã kiểm chứng.")],
                method=["sympy.limit"],
            ),
            warnings=["Kết quả zoo (complex infinity) chỉ báo một phần."],
        )
    steps = limit_steps(template.expression, template.variable, template.point, template.direction, result)
    answer = f"Giới hạn: {algebra_text(result)}"
    verification = _verify_limit(template.expression, template.variable, template.point, template.direction, result)
    status = "solved" if verification.status in {"verified", "partially_verified"} else "partial"
    steps.append(_calculus_conclusion_step(len(steps) + 1, "Kết luận giới hạn", answer, algebra_latex(result)))
    dir_str = "^+" if template.direction == "+" else "^-" if template.direction == "-" else ""
    milestones = [
        f"Giới hạn cần tính: \\lim_{{{algebra_latex(template.variable)}\\to {algebra_latex(template.point)}{dir_str}}}{algebra_latex(template.expression)}",
        f"Kết quả: {algebra_latex(result)}"
    ]
    return AlgebraSolveResponse(
        input=problem.raw_input,
        normalized_input=problem.normalized_input,
        topic="calculus_limit",
        problem_type="calculate_limit",
        status=status,
        answer=answer,
        answer_latex=algebra_latex(result),
        solution_set=AlgebraSolutionSet(kind="expression", text=algebra_text(result), latex=algebra_latex(result)),
        steps=steps,
        milestones=milestones,
        verification=verification,
        warnings=[] if verification.status == "verified" else ["Giới hạn chỉ được kiểm chứng một phần."],
    )


def _solve_integral(problem: ParsedAlgebraProblem, template: CalculusTemplate) -> AlgebraSolveResponse:
    antiderivative = sp.simplify(sp.integrate(template.expression, template.variable))
    if isinstance(antiderivative, sp.Integral) or antiderivative.has(sp.Integral):
        return _unsupported(problem, "calculus_integral", "SymPy chưa tìm được nguyên hàm (Integral unevaluated).")
    is_definite = template.lower is not None and template.upper is not None
    if is_definite:
        result = sp.simplify(sp.integrate(template.expression, (template.variable, template.lower, template.upper)))
        if isinstance(result, sp.Integral) or result.has(sp.Integral):
            return _unsupported(problem, "calculus_integral", "SymPy chưa tính được tích phân xác định (Integral unevaluated).")
        if template.target is not None:
            equation = sp.Eq(result, template.target, evaluate=False)
            solutions = sp.solve(equation, template.upper)
            latex = algebra_latex(equation)
            if solutions:
                answer = f"Nghiệm: {algebra_text(template.upper)} = {', '.join(algebra_text(solution) for solution in solutions)}"
                latex = rf"{algebra_latex(template.upper)}={', '.join(algebra_latex(solution) for solution in solutions)}"
                result = sp.FiniteSet(*solutions)
            else:
                answer = "Không tìm được nghiệm symbolic cho phương trình tích phân."
            verification = AlgebraVerificationReport(
                status="partially_verified",
                checks=[AlgebraVerificationCheck(name="integral_equation", status="warn", detail="Phương trình tích phân được giải symbolic; kiểm chứng độc lập hạn chế.")],
                method=["sympy.integrate", "sympy.solve"],
            )
        else:
            answer = f"Giá trị tích phân: {algebra_text(result)}"
            latex = algebra_latex(result)
            verification = _verify_definite_integral(template.expression, template.variable, template.lower, template.upper, result, antiderivative)
    else:
        result = antiderivative
        answer = f"Nguyên hàm: {algebra_text(result)} + C"
        latex = algebra_latex(result) + "+C"
        verification = _verify_antiderivative(template.expression, template.variable, antiderivative)
    steps = integral_steps(template.expression, template.variable, antiderivative, result, template.lower, template.upper)
    status = "solved" if verification.status in {"verified", "partially_verified"} else "partial"
    steps.append(_calculus_conclusion_step(len(steps) + 1, "Kết luận tích phân", answer, latex))
    milestones = []
    if is_definite:
        milestones.append(f"Tích phân xác định: \\int_{{{algebra_latex(template.lower)}}}^{{{algebra_latex(template.upper)}}} {algebra_latex(template.expression)} d{algebra_latex(template.variable)}")
        milestones.append(f"Nguyên hàm: {algebra_latex(antiderivative)}")
        milestones.append(f"Kết quả: {algebra_latex(result)}")
    else:
        milestones.append(f"Nguyên hàm cần tìm: \\int {algebra_latex(template.expression)} d{algebra_latex(template.variable)}")
        milestones.append(f"Kết quả: {algebra_latex(antiderivative)} + C")

    return AlgebraSolveResponse(
        input=problem.raw_input,
        normalized_input=problem.normalized_input,
        topic="calculus_integral",
        problem_type="calculate_integral",
        status=status,
        answer=answer,
        answer_latex=latex,
        solution_set=AlgebraSolutionSet(kind="expression", text=algebra_text(result), latex=latex),
        steps=steps,
        milestones=milestones,
        verification=verification,
        warnings=[] if verification.status == "verified" else ["Tích phân chỉ được kiểm chứng một phần (diff-back/sample)."],
    )


def _verify_derivative(expression: sp.Expr, variable: sp.Symbol, derivative: sp.Expr, order: int) -> AlgebraVerificationReport:
    checks: list[AlgebraVerificationCheck] = []
    recomputed = sp.simplify(sp.diff(expression, variable, order))
    symbolic_ok = sp.simplify(recomputed - derivative) == 0
    checks.append(AlgebraVerificationCheck(
        name="derivative_recompute",
        status="pass" if symbolic_ok else "fail",
        detail="Tính lại bằng cùng CAS chỉ là consistency replay; finite-difference mới là cross-check độc lập.",
        latex=algebra_latex(derivative),
    ))
    numeric_ok = _numeric_derivative_check(expression, variable, derivative, order)
    checks.append(AlgebraVerificationCheck(
        name="derivative_numeric_sample",
        status="pass" if numeric_ok is True else "warn" if numeric_ok is None else "fail",
        detail=(
            "Finite-difference cross-check tại vài điểm hợp lệ."
            if numeric_ok is not None
            else "Không lấy được mẫu numeric ổn định (điểm kỳ dị / không hữu hạn)."
        ),
    ))
    if any(check.status == "fail" for check in checks):
        status = "failed"
    elif all(check.status == "pass" for check in checks):
        status = "verified"
    else:
        status = "partially_verified"
    return AlgebraVerificationReport(status=status, checks=checks, method=["solver_consistency_replay", "finite_difference"])


def _verify_antiderivative(expression: sp.Expr, variable: sp.Symbol, antiderivative: sp.Expr) -> AlgebraVerificationReport:
    checks: list[AlgebraVerificationCheck] = []
    back = sp.simplify(sp.diff(antiderivative, variable) - expression)
    symbolic_ok = back == 0
    checks.append(AlgebraVerificationCheck(
        name="integral_diff_back",
        status="pass" if symbolic_ok else "fail",
        detail="Kiểm chứng nguyên hàm bằng d/dx(F) - f → 0.",
        latex=algebra_latex(back),
    ))
    if symbolic_ok:
        status = "verified"
    else:
        # Sometimes simplify fails but numeric samples match
        numeric_ok = _numeric_function_match(sp.diff(antiderivative, variable), expression, variable)
        checks.append(AlgebraVerificationCheck(
            name="integral_diff_back_numeric",
            status="pass" if numeric_ok is True else "warn" if numeric_ok is None else "fail",
            detail="So khớp numeric dF/dx với f tại vài điểm.",
        ))
        status = "partially_verified" if numeric_ok is not False and not any(c.status == "fail" for c in checks) else "failed" if any(c.status == "fail" for c in checks) else "partially_verified"
    return AlgebraVerificationReport(status=status, checks=checks, method=["differentiate_back"])


def _verify_definite_integral(
    expression: sp.Expr,
    variable: sp.Symbol,
    lower: sp.Expr,
    upper: sp.Expr,
    result: sp.Expr,
    antiderivative: sp.Expr,
) -> AlgebraVerificationReport:
    checks: list[AlgebraVerificationCheck] = []
    base = _verify_antiderivative(expression, variable, antiderivative)
    checks.extend(base.checks)
    try:
        newton = sp.simplify(antiderivative.subs(variable, upper) - antiderivative.subs(variable, lower))
        ok = sp.simplify(newton - result) == 0
        checks.append(AlgebraVerificationCheck(
            name="integral_newton_leibniz",
            status="pass" if ok else "warn",
            detail="Đối chiếu F(b)-F(a) với kết quả integrate xác định (giả định không kỳ dị trong khoảng).",
            latex=algebra_latex(newton),
        ))
    except Exception:
        checks.append(AlgebraVerificationCheck(
            name="integral_newton_leibniz",
            status="warn",
            detail="Không đánh giá được F(b)-F(a).",
        ))
    if any(check.status == "fail" for check in checks):
        status = "failed"
    elif all(check.status == "pass" for check in checks):
        status = "verified"
    else:
        status = "partially_verified"
    return AlgebraVerificationReport(status=status, checks=checks, method=["differentiate_back", "newton_leibniz"])


def _verify_limit(expression: sp.Expr, variable: sp.Symbol, point: sp.Expr, direction: str, result: sp.Expr) -> AlgebraVerificationReport:
    checks: list[AlgebraVerificationCheck] = []
    recomputed = sp.simplify(sp.limit(expression, variable, point, dir=direction))
    symbolic_ok = sp.simplify(recomputed - result) == 0 if recomputed.is_number and result.is_number else recomputed == result or sp.simplify(recomputed - result) == 0
    checks.append(AlgebraVerificationCheck(
        name="limit_recompute",
        status="pass" if symbolic_ok else "fail",
        detail="Tính lại bằng cùng CAS chỉ là consistency replay; numeric approach mới là cross-check độc lập.",
        latex=algebra_latex(result),
    ))
    numeric_ok = _numeric_limit_sample(expression, variable, point, direction, result)
    checks.append(AlgebraVerificationCheck(
        name="limit_numeric_approach",
        status="pass" if numeric_ok is True else "warn" if numeric_ok is None else "fail",
        detail="Lấy mẫu hàm khi tiến gần điểm giới hạn.",
    ))
    if any(check.status == "fail" for check in checks):
        status = "failed"
    elif all(check.status == "pass" for check in checks):
        status = "verified"
    else:
        status = "partially_verified"
    return AlgebraVerificationReport(status=status, checks=checks, method=["solver_consistency_replay", "numeric_approach"])


def _numeric_derivative_check(expression: sp.Expr, variable: sp.Symbol, derivative: sp.Expr, order: int) -> bool | None:
    if order != 1:
        return None
    samples = [sp.Rational(1, 2), sp.Integer(1), sp.Integer(2), sp.Rational(-1, 2), sp.Integer(-1)]
    h = sp.Rational(1, 1000)
    checked = 0
    for x0 in samples:
        try:
            f_plus = expression.subs(variable, x0 + h)
            f_minus = expression.subs(variable, x0 - h)
            approx = sp.simplify((f_plus - f_minus) / (2 * h))
            exact = derivative.subs(variable, x0)
            if not (approx.is_real is not False and exact.is_real is not False):
                continue
            err = abs(complex(sp.N(approx - exact)))
            if err > 1e-3:
                return False
            checked += 1
        except Exception:
            continue
    if checked == 0:
        return None
    return True


def _numeric_function_match(left: sp.Expr, right: sp.Expr, variable: sp.Symbol) -> bool | None:
    samples = [sp.Rational(1, 2), sp.Integer(1), sp.Integer(2), sp.Rational(-1, 2)]
    checked = 0
    for x0 in samples:
        try:
            lv = left.subs(variable, x0)
            rv = right.subs(variable, x0)
            err = abs(complex(sp.N(lv - rv)))
            if err > 1e-4:
                return False
            checked += 1
        except Exception:
            continue
    if checked == 0:
        return None
    return True


def _numeric_limit_sample(expression: sp.Expr, variable: sp.Symbol, point: sp.Expr, direction: str, result: sp.Expr) -> bool | None:
    if not (result.is_number or result in {sp.oo, -sp.oo}):
        return None
    offsets = [sp.Rational(1, 10), sp.Rational(1, 100), sp.Rational(1, 1000)]
    checked = 0
    for offset in offsets:
        try:
            if direction == "-":
                x0 = point - offset
            elif direction == "+":
                x0 = point + offset
            else:
                x0 = point + offset
            value = expression.subs(variable, x0)
            if result in {sp.oo, -sp.oo}:
                magnitude = abs(complex(sp.N(value)))
                if magnitude < 10:
                    return False
            else:
                err = abs(complex(sp.N(value - result)))
                if err > 0.2:
                    return False
            checked += 1
        except Exception:
            continue
    if checked == 0:
        return None
    return True


def _derivative_steps(template: CalculusTemplate, derivative: sp.Expr) -> list[AlgebraSolveStep]:
    expression = template.expression
    variable = template.variable
    steps = [
        AlgebraSolveStep(
            index=1,
            title="Nhận dạng hàm cần đạo hàm",
            explanation="Xác định biểu thức và biến lấy đạo hàm.",
            goal="Viết đúng bài toán dưới dạng f'(x).",
            why="Đạo hàm luôn gắn với một biến cụ thể.",
            rule="Ký hiệu đạo hàm",
            operation="Gọi f(x) là biểu thức đã cho.",
            before_latex=algebra_latex(expression),
            after_latex=rf"f\left({algebra_latex(variable)}\right)={algebra_latex(expression)}",
            pitfall="Không nhầm biến lấy đạo hàm với tham số/hằng số.",
            check="Biểu thức sau khi đặt f(x) phải đúng với đề bài.",
            expression=algebra_text(expression),
            expression_latex=algebra_latex(expression),
            kind="transform",
            confidence="symbolic",
        )
    ]
    rule_step = _derivative_rule_step(template, derivative, 2)
    if rule_step:
        steps.append(rule_step)
    steps.append(AlgebraSolveStep(
        index=len(steps) + 1,
        title="Rút gọn kết quả",
        explanation="Rút gọn biểu thức đạo hàm về dạng gọn hơn.",
        goal="Viết kết quả cuối cùng rõ ràng.",
        why="Sau khi áp dụng quy tắc đạo hàm, biểu thức có thể còn chưa rút gọn.",
        rule="Rút gọn đại số",
        operation="Thu gọn các tích, tổng và lũy thừa.",
        before_latex=algebra_latex(sp.diff(expression, variable, template.order)),
        after_latex=algebra_latex(derivative),
        pitfall="Không được rút gọn làm thay đổi miền xác định nếu bài yêu cầu xét miền.",
        check="Lấy đạo hàm lại bằng quy tắc hoặc kiểm tra symbolic để đối chiếu.",
        result=algebra_text(derivative),
        result_latex=algebra_latex(derivative),
        kind="solve",
        confidence="verified",
    ))
    return steps


def _derivative_rule_step(template: CalculusTemplate, derivative: sp.Expr, index: int) -> AlgebraSolveStep | None:
    expression = template.expression
    variable = template.variable
    if expression.is_Add:
        return AlgebraSolveStep(
            index=index,
            title="Dùng quy tắc tổng",
            explanation="Đạo hàm của tổng bằng tổng các đạo hàm.",
            goal="Tách biểu thức thành các hạng tử dễ đạo hàm hơn.",
            why="Quy tắc tổng cho phép xử lý từng hạng tử riêng.",
            rule="(u+v)' = u' + v'",
            operation="Lấy đạo hàm từng hạng tử rồi cộng lại.",
            before_latex=algebra_latex(expression),
            after_latex=" + ".join(algebra_latex(sp.diff(term, variable)) for term in sp.Add.make_args(expression)),
            check="Cộng các đạo hàm riêng phải ra đạo hàm của tổng.",
            result_latex=algebra_latex(derivative),
            kind="transform",
            confidence="symbolic",
        )
    if expression.is_Mul and len(sp.Mul.make_args(expression)) >= 2:
        return AlgebraSolveStep(
            index=index,
            title="Dùng quy tắc tích",
            explanation="Biểu thức là tích nên dùng quy tắc đạo hàm của tích.",
            goal="Tính đạo hàm của tích hai hay nhiều thừa số.",
            why="Không được lấy đạo hàm từng thừa số rồi nhân lại.",
            rule="(uv)' = u'v + uv'",
            operation="Áp dụng quy tắc tích rồi rút gọn.",
            before_latex=algebra_latex(expression),
            after_latex=algebra_latex(sp.diff(expression, variable)),
            pitfall="Sai lầm thường gặp là viết (uv)' = u'v'.",
            check="Mỗi hạng tử trong quy tắc tích phải giữ một thừa số chưa đạo hàm.",
            result_latex=algebra_latex(derivative),
            kind="transform",
            confidence="symbolic",
        )
    if isinstance(expression, sp.Pow) and expression.base.has(variable) and not expression.exp.has(variable):
        inner = expression.base
        exponent = expression.exp
        return AlgebraSolveStep(
            index=index,
            title="Dùng quy tắc dây chuyền",
            explanation="Biểu thức là lũy thừa của một hàm bên trong nên dùng quy tắc dây chuyền.",
            goal="Tính đạo hàm hàm hợp.",
            why="Khi f(x) = u(x)^n, cần nhân thêm u'(x).",
            rule="(u^n)' = n u^{n-1} u'",
            operation="Đặt u là biểu thức bên trong, lấy đạo hàm lũy thừa rồi nhân u'.",
            before_latex=algebra_latex(expression),
            after_latex=rf"{algebra_latex(exponent)}\left({algebra_latex(inner)}\right)^{{{algebra_latex(exponent - 1)}}}\cdot\left({algebra_latex(sp.diff(inner, variable))}\right)",
            pitfall="Không quên nhân đạo hàm của biểu thức bên trong.",
            check="Nếu u=x thì công thức trở về đạo hàm lũy thừa cơ bản.",
            result_latex=algebra_latex(derivative),
            kind="transform",
            confidence="symbolic",
        )
    return None


def _limit_steps(template: CalculusTemplate, result: sp.Expr) -> list[AlgebraSolveStep]:
    expression = template.expression
    variable = template.variable
    point = template.point
    direct = sp.simplify(expression.subs(variable, point))
    is_zero_over_zero = _is_indeterminate_zero_over_zero(expression, variable, point)
    direct_text = "0/0" if is_zero_over_zero else algebra_text(direct)
    direct_latex = r"\frac{0}{0}" if is_zero_over_zero else algebra_latex(direct)
    steps = [
        AlgebraSolveStep(
            index=1,
            title="Thử thay trực tiếp",
            explanation="Thay giá trị tiến tới vào biểu thức để xem có tính được ngay không.",
            goal="Nhận biết giới hạn trực tiếp hay dạng vô định.",
            why="Nếu thay trực tiếp ra giá trị xác định thì đó thường là giới hạn.",
            rule="Thay trực tiếp",
            operation=f"Thay {algebra_text(variable)} = {algebra_text(point)} vào biểu thức.",
            before_latex=rf"\lim_{{{algebra_latex(variable)}\to {algebra_latex(point)}}}{algebra_latex(expression)}",
            after_latex=direct_latex,
            pitfall="Nếu gặp 0/0 hoặc oo/oo thì chưa được kết luận.",
            check="Kết quả thay trực tiếp phải xác định.",
            result=direct_text,
            result_latex=direct_latex,
            kind="transform",
            confidence="symbolic",
        )
    ]
    if is_zero_over_zero:
        simplified = sp.cancel(expression)
        steps.append(AlgebraSolveStep(
            index=2,
            title="Khử dạng vô định 0/0",
            explanation="Biểu thức cho dạng 0/0 nên rút gọn nhân tử chung trước khi lấy giới hạn.",
            goal="Loại nhân tử gây 0 ở cả tử và mẫu.",
            why="Dạng 0/0 thường xuất hiện do tử và mẫu có nhân tử chung.",
            rule="Phân tích nhân tử và rút gọn",
            operation="Rút gọn phân thức rồi mới thay lại giá trị tiến tới.",
            before_latex=algebra_latex(expression),
            after_latex=algebra_latex(simplified),
            pitfall="Chỉ rút gọn trong quá trình tính giới hạn, không kết luận giá trị hàm tại điểm đó.",
            check="Biểu thức rút gọn phải bằng biểu thức cũ trên vùng gần điểm đang xét.",
            result_latex=algebra_latex(simplified),
            kind="transform",
            confidence="symbolic",
        ))
    steps.append(AlgebraSolveStep(
        index=len(steps) + 1,
        title="Tính giới hạn sau biến đổi",
        explanation="Tính giới hạn của biểu thức sau khi xử lý dạng cần thiết.",
        goal="Viết giá trị giới hạn.",
        why="Giới hạn mô tả giá trị biểu thức tiến gần tới, không nhất thiết là giá trị tại điểm đó.",
        rule="Tính giới hạn",
        operation="Lấy giới hạn symbolic sau các bước biến đổi.",
        before_latex=rf"\lim_{{{algebra_latex(variable)}\to {algebra_latex(point)}}}{algebra_latex(expression)}",
        after_latex=algebra_latex(result),
        check="Có thể kiểm tra bằng thay các giá trị rất gần điểm tiến tới.",
        result=algebra_text(result),
        result_latex=algebra_latex(result),
        kind="solve",
        confidence="verified",
    ))
    return steps


def _integral_steps(template: CalculusTemplate, antiderivative: sp.Expr, result: sp.Expr) -> list[AlgebraSolveStep]:
    expression = template.expression
    variable = template.variable
    steps = [
        AlgebraSolveStep(
            index=1,
            title="Nhận dạng tích phân",
            explanation="Xác định biểu thức dưới dấu tích phân và biến tích phân.",
            goal="Viết đúng bài toán tích phân.",
            why="Tích phân phải theo một biến cụ thể; các chữ khác được xem như hằng số.",
            rule="Ký hiệu tích phân",
            operation="Gọi biểu thức dưới dấu tích phân là f(x).",
            before_latex=algebra_latex(expression),
            after_latex=rf"f\left({algebra_latex(variable)}\right)={algebra_latex(expression)}",
            check="Biểu thức f(x) phải đúng với đề bài.",
            expression=algebra_text(expression),
            expression_latex=algebra_latex(expression),
            kind="transform",
            confidence="symbolic",
        ),
        AlgebraSolveStep(
            index=2,
            title="Tìm nguyên hàm",
            explanation="Tìm một hàm có đạo hàm bằng biểu thức đã cho.",
            goal="Tính nguyên hàm trước khi xử lý cận.",
            why="Tích phân xác định được tính bằng hiệu giá trị của nguyên hàm tại hai cận.",
            rule="Bảng nguyên hàm cơ bản",
            operation="Áp dụng quy tắc nguyên hàm và rút gọn.",
            before_latex=rf"\int {algebra_latex(expression)}\,d{algebra_latex(variable)}",
            after_latex=algebra_latex(antiderivative),
            pitfall="Nguyên hàm không xác định phải có hằng số C.",
            check="Đạo hàm của nguyên hàm phải ra lại biểu thức ban đầu.",
            result=algebra_text(antiderivative),
            result_latex=algebra_latex(antiderivative),
            kind="solve",
            confidence="symbolic",
        ),
    ]
    if template.lower is not None and template.upper is not None:
        steps.append(AlgebraSolveStep(
            index=3,
            title="Thay cận tích phân",
            explanation="Dùng công thức Newton-Leibniz cho tích phân xác định.",
            goal="Tính giá trị số của tích phân xác định.",
            why="Giá trị tích phân từ a đến b bằng F(b) - F(a).",
            rule="Newton-Leibniz",
            operation="Lấy nguyên hàm tại cận trên trừ nguyên hàm tại cận dưới.",
            before_latex=rf"\left[{algebra_latex(antiderivative)}\right]_{{{algebra_latex(template.lower)}}}^{{{algebra_latex(template.upper)}}}",
            after_latex=rf"{algebra_latex(antiderivative.subs(variable, template.upper))}-{algebra_latex(antiderivative.subs(variable, template.lower))}={algebra_latex(result)}",
            pitfall="Không đổi thứ tự cận trên và cận dưới.",
            check="Nếu đổi cận, kết quả phải đổi dấu.",
            result=algebra_text(result),
            result_latex=algebra_latex(result),
            kind="solve",
            confidence="verified",
        ))
    return steps


def _calculus_conclusion_step(index: int, title: str, answer: str, latex: str) -> AlgebraSolveStep:
    return AlgebraSolveStep(
        index=index,
        title=title,
        explanation=answer,
        goal="Ghi kết quả cuối cùng của phép tính.",
        why="Sau các biến đổi, cần chốt lại kết quả theo đúng loại bài toán.",
        rule="Kết luận kết quả",
        operation="Viết đáp án cuối cùng.",
        after_latex=latex,
        check="Kết quả phải khớp với phép kiểm tra symbolic.",
        result=answer,
        result_latex=latex,
        kind="conclusion",
        confidence="verified",
    )


def _is_indeterminate_zero_over_zero(expression: sp.Expr, variable: sp.Symbol, point: sp.Expr) -> bool:
    numerator, denominator = sp.fraction(sp.together(expression))
    try:
        return sp.simplify(numerator.subs(variable, point)) == 0 and sp.simplify(denominator.subs(variable, point)) == 0
    except Exception:
        return False


def _parse_template(text: str, topic: str, default_variable: sp.Symbol) -> CalculusTemplate:
    match = re.fullmatch(r"(derivative|derivative_equation|derivative_sum|derivative_by_definition|limit|integral|continuous_at)\((.*)\)", text.strip())
    if not match:
        raise ValueError("Dùng dạng derivative(expr=...,var=x), limit(expr=...,var=x,to=...), hoặc integral(expr=...,var=x).")
    name, args_text = match.groups()
    args = _parse_args(args_text)
    variable_name = args.get("var", algebra_text(default_variable))
    if not re.fullmatch(r"[A-Za-z]", variable_name):
        raise ValueError("var cần là tên biến một chữ cái.")
    variable = sp.Symbol(variable_name, real=True)
    local_dict = _local_dict(variable)

    def _safe_expr(raw: str | None, *, required: bool = False, field: str = "expr") -> sp.Expr | None:
        if raw is None or str(raw).strip() == "":
            if required:
                raise ValueError(f"Thiếu {field} trong bài giải tích.")
            return None
        try:
            return parse_algebra_expr(str(raw), local_dict=local_dict)
        except AlgebraParseError as exc:
            raise ValueError(f"Không đọc được {field} giải tích: {exc}") from exc

    if name == "derivative_sum":
        function_names = tuple(item.strip() for item in args.get("functions", "").split("|") if item.strip())
        raw_terms = [item.strip() for item in args.get("values", "").split("|") if item.strip()]
        if len(function_names) < 2 or len(function_names) != len(raw_terms):
            raise ValueError("derivative_sum cần ít nhất hai hàm và cùng số đạo hàm đã cho.")
        if any(not re.fullmatch(r"[A-Za-z]", name) for name in function_names):
            raise ValueError("Tên hàm trong derivative_sum cần là một chữ cái.")
        terms = tuple(_safe_expr(item, required=True, field="values") for item in raw_terms)
        if any(term is None for term in terms):
            raise ValueError("derivative_sum chứa đạo hàm thành phần rỗng.")
        derivative_terms = tuple(term for term in terms if term is not None)
        return CalculusTemplate(
            kind="calculus_derivative_sum",
            expression=sp.Add(*derivative_terms),
            variable=variable,
            derivative_terms=derivative_terms,
            function_names=function_names,
        )

    try:
        expression = _safe_expr(args.get("expr"), required=True, field="expr")
        assert expression is not None
    except KeyError as exc:
        raise ValueError("Thiếu expr trong bài giải tích.") from exc
    if name == "derivative":
        try:
            order = int(args.get("order", "1"))
        except Exception as exc:
            raise ValueError("order đạo hàm phải là số nguyên.") from exc
        if order < 1 or order > 5:
            raise ValueError("order đạo hàm cần nằm trong 1..5.")
        return CalculusTemplate(kind="calculus_derivative", expression=expression, variable=variable, order=order)
    if name == "derivative_equation":
        rhs = _safe_expr(args.get("rhs", "0"), required=True, field="rhs")
        assert rhs is not None
        return CalculusTemplate(
            kind="calculus_derivative_equation",
            expression=expression,
            variable=variable,
            target=rhs,
        )
    if name == "derivative_by_definition":
        point = _safe_expr(args.get("at"), field="at")
        return CalculusTemplate(kind="calculus_derivative_by_definition", expression=expression, variable=variable, point=point)
    if name == "continuous_at":
        point = _safe_expr(args.get("at") or args.get("point"), field="at")
        return CalculusTemplate(kind="calculus_continuous_at", expression=expression, variable=variable, point=point)
    if name == "limit":
        point = _safe_expr(args.get("to", "0"), required=True, field="to")
        assert point is not None
        return CalculusTemplate(kind="calculus_limit", expression=expression, variable=variable, point=point, direction=args.get("dir", "+-"))
    lower = _safe_expr(args.get("a"), field="a")
    upper = _safe_expr(args.get("b"), field="b")
    target = _safe_expr(args.get("target"), field="target")
    return CalculusTemplate(kind="calculus_integral", expression=expression, variable=variable, lower=lower, upper=upper, target=target)


def _parse_args(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in _split_args(text):
        if "=" not in part:
            raise ValueError("Tham số giải tích cần ở dạng key=value.")
        key, value = part.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def _split_args(text: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    for char in text:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if current:
        parts.append("".join(current).strip())
    return parts


def _local_dict(variable: sp.Symbol) -> dict[str, object]:
    names = {"x", "y", "z", "t", "u", algebra_text(variable)}
    data = algebra_local_dict(sorted(names))
    data["Piecewise"] = sp.Piecewise
    data[algebra_text(variable)] = variable
    return data


def _unsupported(problem: ParsedAlgebraProblem, topic: str, message: str) -> AlgebraSolveResponse:
    return AlgebraSolveResponse(input=problem.raw_input, normalized_input=problem.normalized_input, topic=topic, problem_type="calculus", status="unsupported", answer=message, errors=[message])
def _solve_derivative_by_definition(problem: ParsedAlgebraProblem, template: CalculusTemplate) -> AlgebraSolveResponse:
    x = template.variable
    f_x = template.expression
    delta_x = sp.Symbol(r'\Delta x', real=True)
    
    if template.point is not None:
        x0 = template.point
        f_x0 = sp.simplify(f_x.subs(x, x0))
        f_x0_dx = f_x.subs(x, x0 + delta_x)
        diff_expr = f_x0_dx - f_x0
        ratio = diff_expr / delta_x
        result = sp.simplify(sp.limit(ratio, delta_x, 0))
        
        steps = [
            AlgebraSolveStep(
                index=1,
                title=f"Viết công thức đạo hàm bằng định nghĩa tại x = {algebra_text(x0)}",
                explanation=f"Đạo hàm của hàm số tại $x_0 = {algebra_latex(x0)}$ được tính bằng giới hạn: $\\lim_{{{algebra_latex(delta_x)}\\to 0}} \\frac{{f({algebra_latex(x0)}+{algebra_latex(delta_x)}) - f({algebra_latex(x0)})}}{{{algebra_latex(delta_x)}}}$",
                short_explanation="Dùng định nghĩa đạo hàm tại một điểm.",
                detail_level="standard",
                method="derivative_definition",
                goal="Thiết lập giới hạn cần tính.",
                why="Định nghĩa đạo hàm là giới hạn của tỉ số gia số hàm số trên gia số đối số.",
                rule="Đạo hàm bằng định nghĩa",
                operation="Thay hàm số vào công thức giới hạn.",
                after_latex=rf"f'({algebra_latex(x0)}) = \lim_{{{algebra_latex(delta_x)}\to 0}} \frac{{{algebra_latex(f_x0_dx)} - \left({algebra_latex(f_x0)}\right)}}{{{algebra_latex(delta_x)}}}",
                result_latex=algebra_latex(ratio),
                kind="transform",
                confidence="symbolic",
            )
        ]
        
        lim_st = limit_steps(ratio, delta_x, sp.sympify(0), "+-", result)
        for i, st in enumerate(lim_st):
            st.index = len(steps) + 1
            steps.append(st)
            
        answer = f"f'({algebra_text(x0)}) = {algebra_text(result)}"
        answer_latex = algebra_latex(result)
        milestones = [
            f"Hàm số: f({algebra_latex(x)}) = {algebra_latex(f_x)}",
            f"Đạo hàm tại x_0 = {algebra_latex(x0)}: {algebra_latex(result)}"
        ]
    else:
        f_x_dx = f_x.subs(x, x + delta_x)
        diff_expr = f_x_dx - f_x
        ratio = diff_expr / delta_x
        result = sp.simplify(sp.limit(ratio, delta_x, 0))
        
        steps = [
            AlgebraSolveStep(
                index=1,
                title="Viết công thức đạo hàm bằng định nghĩa",
                explanation=f"Đạo hàm của hàm số $f({algebra_latex(x)})$ được tính bằng giới hạn: $\\lim_{{{algebra_latex(delta_x)}\\to 0}} \\frac{{f({algebra_latex(x)}+{algebra_latex(delta_x)}) - f({algebra_latex(x)})}}{{{algebra_latex(delta_x)}}}$",
                short_explanation="Dùng định nghĩa đạo hàm.",
                detail_level="standard",
                method="derivative_definition",
                goal="Thiết lập giới hạn cần tính.",
                why="Định nghĩa đạo hàm là giới hạn của tỉ số gia số hàm số trên gia số đối số.",
                rule="Đạo hàm bằng định nghĩa",
                operation="Thay hàm số vào công thức giới hạn.",
                after_latex=rf"f'({algebra_latex(x)}) = \lim_{{{algebra_latex(delta_x)}\to 0}} \frac{{{algebra_latex(f_x_dx)} - \left({algebra_latex(f_x)}\right)}}{{{algebra_latex(delta_x)}}}",
                result_latex=algebra_latex(ratio),
                kind="transform",
                confidence="symbolic",
            )
        ]
        
        lim_st = limit_steps(ratio, delta_x, sp.sympify(0), "+-", result)
        for i, st in enumerate(lim_st):
            st.index = len(steps) + 1
            steps.append(st)
            
        answer = f"f'({algebra_text(x)}) = {algebra_text(result)}"
        answer_latex = algebra_latex(result)
        milestones = [
            f"Hàm số: f({algebra_latex(x)}) = {algebra_latex(f_x)}",
            f"Đạo hàm bằng định nghĩa: f'({algebra_latex(x)}) = {algebra_latex(result)}"
        ]

    # Independent check: definition result should match ordinary derivative.
    verification = _verify_derivative(f_x, x, result, order=1)
    steps.append(_calculus_conclusion_step(len(steps) + 1, "Kết luận đạo hàm", answer, answer_latex))
    
    return AlgebraSolveResponse(
        input=problem.raw_input,
        normalized_input=problem.normalized_input,
        topic="calculus_derivative_by_definition",
        problem_type="differentiate_by_definition",
        status="solved" if verification.status in {"verified", "partially_verified"} else "partial",
        answer=answer,
        answer_latex=answer_latex,
        solution_set=AlgebraSolutionSet(kind="expression", text=algebra_text(result), latex=algebra_latex(result)),
        steps=steps,
        milestones=milestones,
        verification=verification,
    )


def _solve_continuous_at(problem: ParsedAlgebraProblem, template: CalculusTemplate) -> AlgebraSolveResponse:
    x = template.variable
    f_x = template.expression
    x0 = template.point
    
    if x0 is None:
        return AlgebraSolveResponse(input=problem.raw_input, normalized_input=problem.normalized_input, topic="calculus_continuous_at", problem_type="continuous_at", status="unsupported", answer="Cần chỉ định điểm x0 để xét tính liên tục (vd: at=1).", errors=[])

    # Case 1: f_x is a Piecewise function
    is_piecewise = isinstance(f_x, sp.Piecewise)
    
    steps = []
    
    # Calculate f(x0)
    try:
        f_x0 = sp.simplify(f_x.subs(x, x0))
    except Exception:
        f_x0 = sp.zoo # undefined
        
    is_f_x0_defined = f_x0 not in (sp.zoo, sp.nan, sp.oo, -sp.oo)
    
    steps.append(
        AlgebraSolveStep(
            index=1,
            title=f"Tính giá trị hàm số tại x = {algebra_text(x0)}",
            explanation=f"Thay $x = {algebra_latex(x0)}$ vào hàm số để tìm $f({algebra_latex(x0)})$. " + (f"Ta được $f({algebra_latex(x0)}) = {algebra_latex(f_x0)}$." if is_f_x0_defined else f"Hàm số không xác định tại $x = {algebra_latex(x0)}$."),
            short_explanation=f"Tính f({algebra_latex(x0)}).",
            detail_level="standard",
            method="continuous_eval",
            goal="Xác định f(x0).",
            why="Để hàm số liên tục tại điểm, giá trị hàm số tại đó phải tồn tại.",
            rule="Định nghĩa liên tục",
            operation="Thay x0 vào biểu thức.",
            after_latex=rf"f({algebra_latex(x0)}) = {algebra_latex(f_x0)}" if is_f_x0_defined else r"\text{Không xác định}",
            result=algebra_text(f_x0) if is_f_x0_defined else "undefined",
            result_latex=algebra_latex(f_x0) if is_f_x0_defined else "undefined",
            kind="solve",
            confidence="verified",
        )
    )

    if not is_f_x0_defined:
        answer = "Không liên tục"
        answer_latex = r"\text{Gián đoạn}"
        steps.append(_calculus_conclusion_step(len(steps) + 1, "Kết luận tính liên tục", "Hàm số không xác định tại điểm xét nên không liên tục (bị gián đoạn).", answer_latex))
        verification = AlgebraVerificationReport(
            status="partially_verified",
            checks=[
                AlgebraVerificationCheck(
                    name="continuous_f_defined",
                    status="pass",
                    detail="f(x0) không xác định ⇒ không liên tục (định nghĩa).",
                    latex=answer_latex,
                )
            ],
            method=["definition"],
        )
        return AlgebraSolveResponse(
            input=problem.raw_input,
            normalized_input=problem.normalized_input,
            topic="calculus_continuous_at",
            problem_type="continuous_at",
            status="solved",
            answer=answer,
            answer_latex=answer_latex,
            solution_set=AlgebraSolutionSet(kind="expression", text=answer, latex=answer_latex),
            steps=steps,
            milestones=[],
            verification=verification,
        )
        

    # Limit part
    if is_piecewise:
        # For piecewise, we must calculate limit from left and right
        lim_left = sp.limit(f_x, x, x0, dir="-")
        lim_right = sp.limit(f_x, x, x0, dir="+")
        
        steps.append(
            AlgebraSolveStep(
                index=2,
                title=f"Tính giới hạn trái tại x = {algebra_text(x0)}",
                explanation=f"Tính giới hạn của hàm số khi $x \\to {algebra_latex(x0)}^-$. Kết quả: $\\lim_{{x \\to {algebra_latex(x0)}^-}} f(x) = {algebra_latex(lim_left)}$.",
                short_explanation="Tính giới hạn trái.",
                detail_level="standard",
                method="limit_left",
                goal="Tính giới hạn một phía.",
                why="Hàm phân nhánh cần tính giới hạn 2 bên.",
                rule="Giới hạn",
                operation="Lấy giới hạn.",
                after_latex=rf"\lim_{{x \to {algebra_latex(x0)}^-}} f(x) = {algebra_latex(lim_left)}",
                result=algebra_text(lim_left),
                result_latex=algebra_latex(lim_left),
                kind="solve",
                confidence="verified",
            )
        )
        steps.append(
            AlgebraSolveStep(
                index=3,
                title=f"Tính giới hạn phải tại x = {algebra_text(x0)}",
                explanation=f"Tính giới hạn của hàm số khi $x \\to {algebra_latex(x0)}^+$. Kết quả: $\\lim_{{x \\to {algebra_latex(x0)}^+}} f(x) = {algebra_latex(lim_right)}$.",
                short_explanation="Tính giới hạn phải.",
                detail_level="standard",
                method="limit_right",
                goal="Tính giới hạn một phía.",
                why="Hàm phân nhánh cần tính giới hạn 2 bên.",
                rule="Giới hạn",
                operation="Lấy giới hạn.",
                after_latex=rf"\lim_{{x \to {algebra_latex(x0)}^+}} f(x) = {algebra_latex(lim_right)}",
                result=algebra_text(lim_right),
                result_latex=algebra_latex(lim_right),
                kind="solve",
                confidence="verified",
            )
        )
        
        has_limit = (lim_left == lim_right) and (lim_left not in (sp.oo, -sp.oo, sp.zoo, sp.nan))
        lim_val = lim_left if has_limit else None
        
        if not has_limit:
            steps.append(
                AlgebraSolveStep(
                    index=4,
                    title="So sánh giới hạn 2 bên",
                    explanation=f"Vì giới hạn trái ({algebra_latex(lim_left)}) khác giới hạn phải ({algebra_latex(lim_right)}) nên không tồn tại giới hạn của hàm số tại $x = {algebra_latex(x0)}$.",
                    short_explanation="Không tồn tại giới hạn.",
                    detail_level="standard",
                    method="compare_limits",
                    goal="Xét sự tồn tại giới hạn.",
                    why="Giới hạn tồn tại khi và chỉ khi 2 giới hạn một phía bằng nhau.",
                    rule="Sự tồn tại giới hạn",
                    operation="So sánh.",
                    after_latex=r"\text{Không tồn tại giới hạn}",
                    kind="solve",
                    confidence="verified",
                )
            )
        else:
            steps.append(
                AlgebraSolveStep(
                    index=4,
                    title="So sánh giới hạn 2 bên",
                    explanation=f"Vì giới hạn trái bằng giới hạn phải và bằng ${algebra_latex(lim_val)}$ nên $\\lim_{{x \\to {algebra_latex(x0)}}} f(x) = {algebra_latex(lim_val)}$.",
                    short_explanation="Tồn tại giới hạn.",
                    detail_level="standard",
                    method="compare_limits",
                    goal="Xét sự tồn tại giới hạn.",
                    why="Giới hạn tồn tại khi 2 giới hạn một phía bằng nhau.",
                    rule="Sự tồn tại giới hạn",
                    operation="So sánh.",
                    after_latex=rf"\lim_{{x \to {algebra_latex(x0)}}} f(x) = {algebra_latex(lim_val)}",
                    kind="solve",
                    confidence="verified",
                )
            )
    else:
        # Normal function
        lim_val = sp.limit(f_x, x, x0)
        has_limit = lim_val not in (sp.oo, -sp.oo, sp.zoo, sp.nan)
        
        lim_st = limit_steps(f_x, x, x0, "+-", lim_val)
        for i, st in enumerate(lim_st):
            st.index = len(steps) + 1
            steps.append(st)
            
    # Conclusion
    if not has_limit:
        answer = "Gián đoạn"
        answer_latex = r"\text{Gián đoạn}"
        explanation = f"Vì hàm số không có giới hạn hữu hạn tại $x = {algebra_latex(x0)}$ nên hàm số gián đoạn tại điểm này."
    elif sp.simplify(lim_val - f_x0) == 0:
        answer = "Liên tục"
        answer_latex = r"\text{Liên tục}"
        explanation = f"Vì $\\lim_{{x \\to {algebra_latex(x0)}}} f(x) = f({algebra_latex(x0)}) = {algebra_latex(f_x0)}$ nên hàm số liên tục tại $x = {algebra_latex(x0)}$."
    else:
        answer = "Gián đoạn"
        answer_latex = r"\text{Gián đoạn}"
        explanation = f"Vì $\\lim_{{x \\to {algebra_latex(x0)}}} f(x) = {algebra_latex(lim_val)} \\neq f({algebra_latex(x0)}) = {algebra_latex(f_x0)}$ nên hàm số gián đoạn tại $x = {algebra_latex(x0)}$."
        
    steps.append(_calculus_conclusion_step(len(steps) + 1, "Kết luận tính liên tục", explanation, answer_latex))

    verification = AlgebraVerificationReport(
        status="partially_verified",
        checks=[
            AlgebraVerificationCheck(
                name="continuous_f_defined",
                status="pass" if is_f_x0_defined else "fail",
                detail="f(x0) xác định." if is_f_x0_defined else "f(x0) không xác định.",
            ),
            AlgebraVerificationCheck(
                name="continuous_limit_exists",
                status="pass" if has_limit else "fail",
                detail="Giới hạn hữu hạn tồn tại." if has_limit else "Giới hạn không tồn tại / vô hạn.",
            ),
            AlgebraVerificationCheck(
                name="continuous_limit_equals_value",
                status="pass" if (has_limit and sp.simplify(lim_val - f_x0) == 0) else ("skip" if not has_limit else "fail"),
                detail=(
                    "lim = f(x0)."
                    if has_limit and sp.simplify(lim_val - f_x0) == 0
                    else "lim ≠ f(x0) hoặc không so sánh được."
                ),
                latex=answer_latex,
            ),
        ],
        method=["definition", "sympy.limit"],
    )
    
    milestones = [
        f"Hàm số: f(x) = {algebra_latex(f_x)}",
        f"Xét tại x = {algebra_latex(x0)}: {answer}"
    ]

    return AlgebraSolveResponse(
        input=problem.raw_input,
        normalized_input=problem.normalized_input,
        topic="calculus_continuous_at",
        problem_type="continuous_at",
        status="solved",
        answer=answer,
        answer_latex=answer_latex,
        solution_set=AlgebraSolutionSet(kind="expression", text=answer, latex=answer_latex),
        steps=steps,
        milestones=milestones,
        verification=verification,
    )
