from __future__ import annotations

import re
from dataclasses import dataclass

import sympy as sp

from app.schemas.algebra import AlgebraSolutionSet, AlgebraSolveResponse, AlgebraSolveStep, AlgebraVerificationCheck, AlgebraVerificationReport
from app.services.algebra.parser import ParsedAlgebraProblem
from app.services.algebra.steps import conclusion_step


@dataclass(frozen=True)
class QuadraticTemplate:
    kind: str
    a: sp.Expr
    b: sp.Expr
    c: sp.Expr
    variable: sp.Symbol
    parameter: sp.Symbol


def solve_parameter(problem: ParsedAlgebraProblem) -> AlgebraSolveResponse:
    normalized = problem.normalized_input.strip()
    steps: list[AlgebraSolveStep] = []
    try:
        template = _parse_quadratic_template(normalized)
        condition, explanation, latex = _solve_quadratic_template(template)
    except ValueError as exc:
        return _unsupported(problem, str(exc))

    condition_text = sp.sstr(condition)
    condition_latex = sp.latex(condition)
    steps.append(AlgebraSolveStep(
        index=1,
        title="Tính biệt thức Delta",
        explanation="Với bài toán tham số bậc hai, trước hết tính Delta theo tham số.",
        goal="Đưa điều kiện nghiệm về điều kiện của Delta.",
        why="Số nghiệm thực của phương trình bậc hai được quyết định bởi dấu của Delta.",
        rule="Biệt thức bậc hai",
        operation="Tính Delta = b^2 - 4ac từ các hệ số a, b, c.",
        expression=_quadratic_expression_text(template),
        expression_latex=_quadratic_equation_latex(template),
        result=sp.sstr(template.b ** 2 - 4 * template.a * template.c),
        result_latex=latex,
        kind="transform",
        confidence="symbolic",
    ))
    steps.append(AlgebraSolveStep(
        index=2,
        title="Lập điều kiện theo tham số",
        explanation=explanation,
        goal="Tìm các giá trị tham số làm bài toán thỏa yêu cầu.",
        why="Mỗi yêu cầu như nghiệm kép, hai nghiệm phân biệt hay vô nghiệm tương ứng với một điều kiện về Delta.",
        rule="Điều kiện nghiệm bậc hai",
        operation="Đổi yêu cầu của đề thành bất phương trình hoặc phương trình theo tham số.",
        expression=_quadratic_expression_text(template),
        expression_latex=latex,
        result=condition_text,
        result_latex=condition_latex,
        kind="solve",
        confidence="symbolic",
    ))
    verification = _verify_quadratic_template(template, condition)
    answer = f"Điều kiện tham số: {condition_text}"
    steps.append(conclusion_step(3, answer, condition_latex))
    
    milestones = [
        f"Phương trình gốc: {_quadratic_equation_latex(template)}",
        f"Điều kiện: {latex}",
        f"Kết quả: {condition_latex}"
    ]
    
    return AlgebraSolveResponse(
        input=problem.raw_input,
        normalized_input=problem.normalized_input,
        topic="parameter",
        problem_type=template.kind,
        status="solved" if verification.status == "verified" else "partial",
        answer=answer,
        answer_latex=condition_latex,
        solution_set=AlgebraSolutionSet(kind="conditions", text=condition_text, latex=condition_latex),
        steps=steps,
        milestones=milestones,
        verification=verification,
        assumptions=["Template tham số hiện hỗ trợ phương trình/bất phương trình bậc hai một tham số."],
        warnings=[] if verification.status == "verified" else ["Điều kiện tham số chỉ được kiểm chứng bằng mẫu đại diện."],
        errors=[],
    )


def _parse_quadratic_template(text: str) -> QuadraticTemplate:
    match = re.fullmatch(r"(quadratic_double_root|quadratic_has_two_roots|quadratic_has_real_root|quadratic_no_real_root|quadratic_positive_all)\((.*)\)", text)
    if not match:
        raise ValueError("Dạng tham số này chưa được hỗ trợ. Hãy dùng quadratic_double_root(...), quadratic_has_two_roots(...), quadratic_has_real_root(...), quadratic_no_real_root(...) hoặc quadratic_positive_all(...).")
    kind, args_text = match.groups()
    args = _parse_args(args_text)
    variable_name = args.get("var", "x")
    parameter_name = args.get("param", "m")
    if not re.fullmatch(r"[A-Za-z]", variable_name) or not re.fullmatch(r"[A-Za-z]", parameter_name):
        raise ValueError("var và param cần là tên một chữ cái.")
    variable = sp.Symbol(variable_name, real=True)
    parameter = sp.Symbol(parameter_name, real=True)
    local_dict = {
        variable_name: variable,
        parameter_name: parameter,
        "sqrt": sp.sqrt,
        "pi": sp.pi,
        "E": sp.E,
    }
    try:
        a = sp.sympify(args.get("a", "1"), locals=local_dict)
        b = sp.sympify(args["b"], locals=local_dict)
        c = sp.sympify(args["c"], locals=local_dict)
    except KeyError as exc:
        raise ValueError("Template bậc hai cần đủ a, b, c.") from exc
    except Exception as exc:
        raise ValueError(f"Không đọc được hệ số bậc hai: {exc}") from exc
    if sp.simplify(a) == 0:
        raise ValueError("Hệ số a phải khác 0 để là bài toán bậc hai.")
    return QuadraticTemplate(kind=kind, a=a, b=b, c=c, variable=variable, parameter=parameter)


def _parse_args(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in _split_args(text):
        if "=" not in part:
            raise ValueError("Tham số template cần ở dạng key=value.")
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


def _solve_quadratic_template(template: QuadraticTemplate) -> tuple[sp.Expr, str, str]:
    delta = sp.factor(template.b ** 2 - 4 * template.a * template.c)
    parameter = template.parameter
    if template.kind == "quadratic_double_root":
        condition = sp.solveset(delta, parameter, domain=sp.S.Reals)
        explanation = "Phương trình bậc hai có nghiệm kép khi discriminant bằng 0."
    elif template.kind == "quadratic_has_two_roots":
        condition = sp.solve_univariate_inequality(delta > 0, parameter, relational=False)
        explanation = "Phương trình bậc hai có hai nghiệm thực phân biệt khi discriminant dương."
    elif template.kind == "quadratic_has_real_root":
        condition = sp.solve_univariate_inequality(delta >= 0, parameter, relational=False)
        explanation = "Phương trình bậc hai có nghiệm thực khi discriminant không âm."
    elif template.kind == "quadratic_no_real_root":
        condition = sp.solve_univariate_inequality(delta < 0, parameter, relational=False)
        explanation = "Phương trình bậc hai vô nghiệm thực khi discriminant âm."
    elif template.kind == "quadratic_positive_all":
        delta_condition = sp.solve_univariate_inequality(delta < 0, parameter, relational=True)
        condition = sp.And(template.a > 0, delta_condition)
        condition = sp.simplify(condition)
        explanation = "Tam thức bậc hai dương với mọi x khi a dương và discriminant âm."
    else:
        raise ValueError("Template tham số chưa được hỗ trợ.")
    latex = f"\Delta = {sp.latex(delta)}"
    return condition, explanation, latex


def _verify_quadratic_template(template: QuadraticTemplate, condition: sp.Expr) -> AlgebraVerificationReport:
    checks = [AlgebraVerificationCheck(name="parameter_template_rule", status="pass", detail="Áp dụng quy tắc discriminant chuẩn cho tam thức bậc hai.")]
    sample_check = _sample_check(template, condition)
    checks.append(sample_check)
    status = "verified" if all(check.status == "pass" for check in checks) else "partially_verified"
    return AlgebraVerificationReport(status=status, checks=checks, method=["symbolic_discriminant", "sample_substitution"])


def _sample_check(template: QuadraticTemplate, condition: sp.Expr) -> AlgebraVerificationCheck:
    samples = [-3, -2, -1, 0, 1, 2, 3]
    tested = 0
    for value in samples:
        try:
            expected = bool(condition.contains(value)) if isinstance(condition, sp.Set) else bool(condition.subs(template.parameter, value))
            actual = _actual_property(template, value)
        except Exception:
            continue
        if expected != actual:
            return AlgebraVerificationCheck(name="parameter_sample_check", status="fail", detail=f"Kiểm tra mẫu m = {value} không khớp với điều kiện tìm được.")
        tested += 1
    if tested == 0:
        return AlgebraVerificationCheck(name="parameter_sample_check", status="warn", detail="Không tìm được mẫu số nguyên nhỏ để kiểm tra điều kiện tham số.")
    return AlgebraVerificationCheck(name="parameter_sample_check", status="pass", detail=f"Đã kiểm tra {tested} giá trị tham số nguyên nhỏ và đều khớp.")


def _actual_property(template: QuadraticTemplate, parameter_value: int) -> bool:
    a = sp.simplify(template.a.subs(template.parameter, parameter_value))
    b = sp.simplify(template.b.subs(template.parameter, parameter_value))
    c = sp.simplify(template.c.subs(template.parameter, parameter_value))
    delta = sp.simplify(b ** 2 - 4 * a * c)
    if template.kind == "quadratic_double_root":
        return delta == 0
    if template.kind == "quadratic_has_two_roots":
        return bool(delta > 0)
    if template.kind == "quadratic_has_real_root":
        return bool(delta >= 0)
    if template.kind == "quadratic_no_real_root":
        return bool(delta < 0)
    if template.kind == "quadratic_positive_all":
        return bool(a > 0 and delta < 0)
    return False


def _quadratic_expression_text(template: QuadraticTemplate) -> str:
    expression = template.a * template.variable ** 2 + template.b * template.variable + template.c
    return sp.sstr(sp.expand(expression))


def _quadratic_equation_latex(template: QuadraticTemplate) -> str:
    expression = template.a * template.variable ** 2 + template.b * template.variable + template.c
    return sp.latex(sp.Eq(sp.expand(expression), 0, evaluate=False))


def _unsupported(problem: ParsedAlgebraProblem, message: str) -> AlgebraSolveResponse:
    return AlgebraSolveResponse(input=problem.raw_input, normalized_input=problem.normalized_input, topic="parameter", problem_type="parameter_template", status="unsupported", answer=message, errors=[message])
