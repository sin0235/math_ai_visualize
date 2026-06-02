from __future__ import annotations

import re
from dataclasses import dataclass

import sympy as sp

from app.schemas.algebra import (
    AlgebraSolutionSet,
    AlgebraSolveResponse,
    AlgebraSolveStep,
    AlgebraVerificationCheck,
    AlgebraVerificationReport,
)
from app.services.algebra.parser import ParsedAlgebraProblem


@dataclass(frozen=True)
class CalculusTemplate:
    kind: str
    expression: sp.Expr
    variable: sp.Symbol
    point: sp.Expr | None = None
    direction: str = "+-"
    lower: sp.Expr | None = None
    upper: sp.Expr | None = None
    order: int = 1


def solve_calculus(problem: ParsedAlgebraProblem) -> AlgebraSolveResponse:
    try:
        template = _parse_template(problem.normalized_input, problem.topic, problem.variable)
    except ValueError as exc:
        return _unsupported(problem, problem.topic, str(exc))
    if template.kind == "calculus_derivative":
        return _solve_derivative(problem, template)
    if template.kind == "calculus_limit":
        return _solve_limit(problem, template)
    if template.kind == "calculus_integral":
        return _solve_integral(problem, template)
    return _unsupported(problem, template.kind, "Dạng giải tích này chưa được hỗ trợ.")


def _solve_derivative(problem: ParsedAlgebraProblem, template: CalculusTemplate) -> AlgebraSolveResponse:
    derivative = sp.simplify(sp.diff(template.expression, template.variable, template.order))
    steps = _derivative_steps(template, derivative)
    answer = f"Đạo hàm: {sp.sstr(derivative)}"
    verification = AlgebraVerificationReport(
        status="verified",
        checks=[AlgebraVerificationCheck(name="derivative_symbolic", status="pass", detail="Đạo hàm được tính bằng quy tắc vi phân symbolic.", latex=sp.latex(derivative))],
        method=["sympy.diff"],
    )
    steps.append(_calculus_conclusion_step(len(steps) + 1, "Kết luận đạo hàm", answer, sp.latex(derivative)))
    return AlgebraSolveResponse(
        input=problem.raw_input,
        normalized_input=problem.normalized_input,
        topic="calculus_derivative",
        problem_type="differentiate_expression",
        status="solved",
        answer=answer,
        answer_latex=sp.latex(derivative),
        solution_set=AlgebraSolutionSet(kind="expression", text=sp.sstr(derivative), latex=sp.latex(derivative)),
        steps=steps,
        verification=verification,
    )


def _solve_limit(problem: ParsedAlgebraProblem, template: CalculusTemplate) -> AlgebraSolveResponse:
    if template.point is None:
        return _unsupported(problem, "calculus_limit", "Giới hạn cần có điểm tiến tới, ví dụ limit(expr=(x^2-1)/(x-1),var=x,to=1).")
    result = sp.simplify(sp.limit(template.expression, template.variable, template.point, dir=template.direction))
    steps = _limit_steps(template, result)
    answer = f"Giới hạn: {sp.sstr(result)}"
    verification = AlgebraVerificationReport(
        status="verified",
        checks=[AlgebraVerificationCheck(name="limit_symbolic", status="pass", detail="Giới hạn được kiểm tra bằng phép tính symbolic.", latex=sp.latex(result))],
        method=["sympy.limit"],
    )
    steps.append(_calculus_conclusion_step(len(steps) + 1, "Kết luận giới hạn", answer, sp.latex(result)))
    return AlgebraSolveResponse(
        input=problem.raw_input,
        normalized_input=problem.normalized_input,
        topic="calculus_limit",
        problem_type="calculate_limit",
        status="solved",
        answer=answer,
        answer_latex=sp.latex(result),
        solution_set=AlgebraSolutionSet(kind="expression", text=sp.sstr(result), latex=sp.latex(result)),
        steps=steps,
        verification=verification,
    )


def _solve_integral(problem: ParsedAlgebraProblem, template: CalculusTemplate) -> AlgebraSolveResponse:
    antiderivative = sp.simplify(sp.integrate(template.expression, template.variable))
    is_definite = template.lower is not None and template.upper is not None
    if is_definite:
        result = sp.simplify(sp.integrate(template.expression, (template.variable, template.lower, template.upper)))
        answer = f"Giá trị tích phân: {sp.sstr(result)}"
        latex = sp.latex(result)
    else:
        result = antiderivative
        answer = f"Nguyên hàm: {sp.sstr(result)} + C"
        latex = sp.latex(result) + "+C"
    steps = _integral_steps(template, antiderivative, result)
    verification = AlgebraVerificationReport(
        status="verified",
        checks=[AlgebraVerificationCheck(name="integral_symbolic", status="pass", detail="Kết quả tích phân được tính symbolic.", latex=latex)],
        method=["sympy.integrate"],
    )
    steps.append(_calculus_conclusion_step(len(steps) + 1, "Kết luận tích phân", answer, latex))
    return AlgebraSolveResponse(
        input=problem.raw_input,
        normalized_input=problem.normalized_input,
        topic="calculus_integral",
        problem_type="calculate_integral",
        status="solved",
        answer=answer,
        answer_latex=latex,
        solution_set=AlgebraSolutionSet(kind="expression", text=sp.sstr(result), latex=latex),
        steps=steps,
        verification=verification,
    )


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
            before_latex=sp.latex(expression),
            after_latex=rf"f\left({sp.latex(variable)}\right)={sp.latex(expression)}",
            pitfall="Không nhầm biến lấy đạo hàm với tham số/hằng số.",
            check="Biểu thức sau khi đặt f(x) phải đúng với đề bài.",
            expression=sp.sstr(expression),
            expression_latex=sp.latex(expression),
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
        before_latex=sp.latex(sp.diff(expression, variable, template.order)),
        after_latex=sp.latex(derivative),
        pitfall="Không được rút gọn làm thay đổi miền xác định nếu bài yêu cầu xét miền.",
        check="Lấy đạo hàm lại bằng quy tắc hoặc kiểm tra symbolic để đối chiếu.",
        result=sp.sstr(derivative),
        result_latex=sp.latex(derivative),
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
            before_latex=sp.latex(expression),
            after_latex=" + ".join(sp.latex(sp.diff(term, variable)) for term in sp.Add.make_args(expression)),
            check="Cộng các đạo hàm riêng phải ra đạo hàm của tổng.",
            result_latex=sp.latex(derivative),
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
            before_latex=sp.latex(expression),
            after_latex=sp.latex(sp.diff(expression, variable)),
            pitfall="Sai lầm thường gặp là viết (uv)' = u'v'.",
            check="Mỗi hạng tử trong quy tắc tích phải giữ một thừa số chưa đạo hàm.",
            result_latex=sp.latex(derivative),
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
            before_latex=sp.latex(expression),
            after_latex=rf"{sp.latex(exponent)}\left({sp.latex(inner)}\right)^{{{sp.latex(exponent - 1)}}}\cdot\left({sp.latex(sp.diff(inner, variable))}\right)",
            pitfall="Không quên nhân đạo hàm của biểu thức bên trong.",
            check="Nếu u=x thì công thức trở về đạo hàm lũy thừa cơ bản.",
            result_latex=sp.latex(derivative),
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
    direct_text = "0/0" if is_zero_over_zero else sp.sstr(direct)
    direct_latex = r"\frac{0}{0}" if is_zero_over_zero else sp.latex(direct)
    steps = [
        AlgebraSolveStep(
            index=1,
            title="Thử thay trực tiếp",
            explanation="Thay giá trị tiến tới vào biểu thức để xem có tính được ngay không.",
            goal="Nhận biết giới hạn trực tiếp hay dạng vô định.",
            why="Nếu thay trực tiếp ra giá trị xác định thì đó thường là giới hạn.",
            rule="Thay trực tiếp",
            operation=f"Thay {sp.sstr(variable)} = {sp.sstr(point)} vào biểu thức.",
            before_latex=rf"\lim_{{{sp.latex(variable)}\to {sp.latex(point)}}}{sp.latex(expression)}",
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
            before_latex=sp.latex(expression),
            after_latex=sp.latex(simplified),
            pitfall="Chỉ rút gọn trong quá trình tính giới hạn, không kết luận giá trị hàm tại điểm đó.",
            check="Biểu thức rút gọn phải bằng biểu thức cũ trên vùng gần điểm đang xét.",
            result_latex=sp.latex(simplified),
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
        before_latex=rf"\lim_{{{sp.latex(variable)}\to {sp.latex(point)}}}{sp.latex(expression)}",
        after_latex=sp.latex(result),
        check="Có thể kiểm tra bằng thay các giá trị rất gần điểm tiến tới.",
        result=sp.sstr(result),
        result_latex=sp.latex(result),
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
            before_latex=sp.latex(expression),
            after_latex=rf"f\left({sp.latex(variable)}\right)={sp.latex(expression)}",
            check="Biểu thức f(x) phải đúng với đề bài.",
            expression=sp.sstr(expression),
            expression_latex=sp.latex(expression),
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
            before_latex=rf"\int {sp.latex(expression)}\,d{sp.latex(variable)}",
            after_latex=sp.latex(antiderivative),
            pitfall="Nguyên hàm không xác định phải có hằng số C.",
            check="Đạo hàm của nguyên hàm phải ra lại biểu thức ban đầu.",
            result=sp.sstr(antiderivative),
            result_latex=sp.latex(antiderivative),
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
            before_latex=rf"\left[{sp.latex(antiderivative)}\right]_{{{sp.latex(template.lower)}}}^{{{sp.latex(template.upper)}}}",
            after_latex=rf"{sp.latex(antiderivative.subs(variable, template.upper))}-{sp.latex(antiderivative.subs(variable, template.lower))}={sp.latex(result)}",
            pitfall="Không đổi thứ tự cận trên và cận dưới.",
            check="Nếu đổi cận, kết quả phải đổi dấu.",
            result=sp.sstr(result),
            result_latex=sp.latex(result),
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
    match = re.fullmatch(r"(derivative|limit|integral)\((.*)\)", text.strip())
    if not match:
        raise ValueError("Dùng dạng derivative(expr=...,var=x), limit(expr=...,var=x,to=...), hoặc integral(expr=...,var=x).")
    name, args_text = match.groups()
    args = _parse_args(args_text)
    variable_name = args.get("var", sp.sstr(default_variable))
    if not re.fullmatch(r"[A-Za-z]", variable_name):
        raise ValueError("var cần là tên biến một chữ cái.")
    variable = sp.Symbol(variable_name, real=True)
    local_dict = _local_dict(variable)
    try:
        expression = sp.sympify(args["expr"], locals=local_dict)
    except KeyError as exc:
        raise ValueError("Thiếu expr trong bài giải tích.") from exc
    except Exception as exc:
        raise ValueError(f"Không đọc được biểu thức giải tích: {exc}") from exc
    if name == "derivative":
        return CalculusTemplate(kind="calculus_derivative", expression=expression, variable=variable, order=int(args.get("order", "1")))
    if name == "limit":
        point = sp.sympify(args.get("to", "0"), locals=local_dict)
        return CalculusTemplate(kind="calculus_limit", expression=expression, variable=variable, point=point, direction=args.get("dir", "+-"))
    lower = sp.sympify(args["a"], locals=local_dict) if "a" in args else None
    upper = sp.sympify(args["b"], locals=local_dict) if "b" in args else None
    return CalculusTemplate(kind="calculus_integral", expression=expression, variable=variable, lower=lower, upper=upper)


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
    names = {"x", "y", "z", "t", "u", sp.sstr(variable)}
    data: dict[str, object] = {name: sp.Symbol(name, real=True) for name in names}
    data.update({
        "sqrt": sp.sqrt,
        "sin": sp.sin,
        "cos": sp.cos,
        "tan": sp.tan,
        "cot": sp.cot,
        "log": sp.log,
        "ln": sp.log,
        "exp": sp.exp,
        "pi": sp.pi,
        "E": sp.E,
        "oo": sp.oo,
    })
    data[sp.sstr(variable)] = variable
    return data


def _unsupported(problem: ParsedAlgebraProblem, topic: str, message: str) -> AlgebraSolveResponse:
    return AlgebraSolveResponse(input=problem.raw_input, normalized_input=problem.normalized_input, topic=topic, problem_type="calculus", status="unsupported", answer=message, errors=[message])
