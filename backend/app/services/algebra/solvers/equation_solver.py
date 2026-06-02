from __future__ import annotations

import sympy as sp

from app.schemas.algebra import AlgebraSolutionSet, AlgebraSolutionValue, AlgebraSolveResponse, AlgebraSolveStep
from app.services.algebra.domain import domain_assumptions_from_expression
from app.services.algebra.formatting import format_solution_set, solution_values
from app.services.algebra.parser import ParsedAlgebraProblem
from app.services.algebra.steps import conclusion_step, domain_step
from app.services.algebra.verifier import verify_finite_solutions, verify_solution_set


def solve_equation(problem: ParsedAlgebraProblem) -> AlgebraSolveResponse:
    if problem.relation is None or not isinstance(problem.relation, sp.Equality):
        return _unsupported(problem, "Đầu vào không phải phương trình.")
    variable = problem.variable
    expression = sp.simplify(problem.relation.lhs - problem.relation.rhs)
    assumptions = domain_assumptions_from_expression(expression, variable)
    steps: list[AlgebraSolveStep] = []
    if assumptions:
        steps.append(domain_step(len(steps) + 1, assumptions))
    try:
        solution_set = sp.solveset(expression, variable, domain=sp.S.Reals if problem.domain == "R" else sp.S.Complexes)
    except Exception as exc:
        return _unsupported(problem, f"SymPy chưa giải được phương trình này: {exc}")
    steps.extend(_technique_steps(problem, expression, variable, len(steps) + 1))
    detailed_steps = (
        _factor_steps(expression, variable, start_index=len(steps) + 1)
        or _quadratic_steps(expression, variable, start_index=len(steps) + 1)
        or _depressed_cubic_steps(expression, variable, start_index=len(steps) + 1)
    )
    if detailed_steps:
        steps.extend(detailed_steps)
    else:
        steps.append(AlgebraSolveStep(
            index=len(steps) + 1,
            title="Giải phương trình",
            explanation="Tìm các giá trị làm hai vế của phương trình bằng nhau.",
            goal="Tìm các nghiệm ứng viên của phương trình.",
            why="Một phương trình A = B tương đương với A - B = 0, nên ta có thể giải biểu thức một vế.",
            rule="Chuyển vế và giải phương trình",
            operation="Lấy vế trái trừ vế phải, rút gọn, rồi giải trên miền đã chọn.",
            before_latex=sp.latex(problem.relation),
            after_latex=sp.latex(sp.Eq(expression, 0, evaluate=False)),
            pitfall="Các nghiệm ứng viên vẫn cần kiểm tra lại với điều kiện xác định của đề gốc.",
            check="Thay từng nghiệm ứng viên vào phương trình gốc để xác nhận.",
            expression=sp.sstr(expression),
            expression_latex=sp.latex(expression),
            result=sp.sstr(solution_set),
            result_latex=sp.latex(solution_set),
            kind="solve",
            confidence="symbolic",
        ))
    values = solution_values(solution_set)
    answer, answer_latex = _display_answer(expression, variable, solution_set, values)
    solution = AlgebraSolutionSet(
        kind="empty" if solution_set is sp.EmptySet else "finite" if values is not None else "set",
        text=answer,
        latex=sp.latex(solution_set),
        values=[AlgebraSolutionValue(text=sp.sstr(value), latex=sp.latex(value), approximate=str(sp.N(value, 8))) for value in values or []],
    )
    verification = verify_finite_solutions(problem, values) if values is not None else verify_solution_set(problem, solution_set)
    status = "solved" if verification.status in {"verified", "partially_verified"} else "error"
    if values is not None and _needs_filter_step(expression, variable):
        steps.append(_filter_candidates_step(len(steps) + 1, problem, values))
    steps.append(_verification_step(len(steps) + 1, verification.status, values, solution_set, problem, expression))
    steps.append(conclusion_step(len(steps) + 1, answer, answer_latex))
    return AlgebraSolveResponse(
        input=problem.raw_input,
        normalized_input=problem.normalized_input,
        topic="equation",
        problem_type="solve_equation",
        status=status,
        answer=answer,
        answer_latex=answer_latex,
        solution_set=solution,
        steps=steps,
        verification=verification,
        assumptions=assumptions,
        warnings=[] if values is not None else ["Tập nghiệm symbolic không hữu hạn nên chỉ kiểm chứng ở mức biểu diễn tập nghiệm."],
        errors=[] if status == "solved" else ["Kiểm chứng nghiệm thất bại."],
    )


def _unsupported(problem: ParsedAlgebraProblem, message: str) -> AlgebraSolveResponse:
    return AlgebraSolveResponse(input=problem.raw_input, normalized_input=problem.normalized_input, topic="equation", problem_type="solve_equation", status="unsupported", answer=message, errors=[message])


def _technique_steps(problem: ParsedAlgebraProblem, expression: sp.Expr, variable: sp.Symbol, start_index: int) -> list[AlgebraSolveStep]:
    steps: list[AlgebraSolveStep] = []
    rational_step = _rational_clear_denominator_step(problem, expression, variable, start_index)
    if rational_step:
        steps.append(rational_step)
    radical_step = _radical_method_step(problem, expression, variable, start_index + len(steps))
    if radical_step:
        steps.append(radical_step)
    return steps


def _rational_clear_denominator_step(problem: ParsedAlgebraProblem, expression: sp.Expr, variable: sp.Symbol, index: int) -> AlgebraSolveStep | None:
    rational_expression = sp.together(expression)
    numerator, denominator = sp.fraction(rational_expression)
    if denominator == 1 or not denominator.has(variable):
        return None
    numerator = sp.factor(numerator)
    denominator = sp.factor(denominator)
    return AlgebraSolveStep(
        index=index,
        title="Quy đồng và khử mẫu",
        explanation="Vì phương trình có phân thức, trước hết cần ghi điều kiện mẫu khác 0 rồi đưa về phương trình tử số bằng 0.",
        goal="Loại mẫu số khỏi phương trình nhưng vẫn giữ điều kiện xác định.",
        why="Một phân thức bằng 0 khi tử số bằng 0 và mẫu số khác 0.",
        rule="Khử mẫu phân thức",
        operation="Quy đồng biểu thức hai vế, giữ điều kiện mẫu khác 0, rồi xét tử số bằng 0.",
        before_latex=sp.latex(problem.relation) if problem.relation is not None else sp.latex(expression),
        after_latex=sp.latex(sp.Eq(numerator, 0, evaluate=False)),
        pitfall="Không được nhân chéo rồi quên loại giá trị làm mẫu bằng 0.",
        check=f"Sau khi tìm nghiệm, thay lại để chắc chắn {sp.sstr(denominator)} khác 0.",
        expression=sp.sstr(rational_expression),
        expression_latex=sp.latex(rational_expression),
        result=sp.sstr(numerator),
        result_latex=sp.latex(sp.Eq(numerator, 0, evaluate=False)),
        kind="transform",
        confidence="symbolic",
    )


def _radical_method_step(problem: ParsedAlgebraProblem, expression: sp.Expr, variable: sp.Symbol, index: int) -> AlgebraSolveStep | None:
    if not _has_even_root(expression, variable):
        return None
    return AlgebraSolveStep(
        index=index,
        title="Khử căn thức",
        explanation="Phương trình có căn thức nên cần cô lập căn hoặc dùng liên hợp/bình phương để đưa về phương trình quen thuộc hơn.",
        goal="Biến phương trình chứa căn thành phương trình không còn căn ở bước giải chính.",
        why="Căn thức làm giới hạn miền xác định và các phép bình phương có thể sinh nghiệm ngoại lai.",
        rule="Cô lập căn, nhân liên hợp hoặc bình phương hai vế",
        operation="Xác định phần chứa căn, biến đổi tương đương khi có thể, rồi kiểm tra nghiệm tìm được với phương trình gốc.",
        before_latex=sp.latex(problem.relation) if problem.relation is not None else sp.latex(expression),
        after_latex=sp.latex(sp.Eq(expression, 0, evaluate=False)),
        pitfall="Bình phương hai vế không luôn là phép tương đương hai chiều; bắt buộc thử lại nghiệm.",
        check="Nghiệm cuối cùng phải làm biểu thức trong căn không âm và thỏa phương trình ban đầu.",
        expression=sp.sstr(expression),
        expression_latex=sp.latex(expression),
        kind="transform",
        confidence="symbolic",
    )


def _has_even_root(expression: sp.Expr, variable: sp.Symbol) -> bool:
    for power in expression.atoms(sp.Pow):
        if power.base.has(variable) and power.exp.is_Rational and power.exp.q % 2 == 0:
            return True
    return False


def _needs_filter_step(expression: sp.Expr, variable: sp.Symbol) -> bool:
    denominator = sp.denom(sp.together(expression))
    if denominator != 1 and denominator.has(variable):
        return True
    if _has_even_root(expression, variable):
        return True
    return any(log_expr.args[0].has(variable) for log_expr in expression.atoms(sp.log))


def _filter_candidates_step(index: int, problem: ParsedAlgebraProblem, values: list[sp.Expr]) -> AlgebraSolveStep:
    candidates = ", ".join(sp.latex(value) for value in values) if values else r"\varnothing"
    return AlgebraSolveStep(
        index=index,
        title="Lọc nghiệm theo điều kiện gốc",
        explanation="Giữ lại những nghiệm vừa thỏa điều kiện xác định vừa làm đúng phương trình ban đầu.",
        goal="Loại nghiệm không hợp lệ trước khi kết luận.",
        why="Một số phép biến đổi như khử mẫu, logarit hoặc căn thức có thể tạo nghiệm ứng viên không dùng được trong đề gốc.",
        rule="Thử lại nghiệm vào phương trình gốc",
        operation="Đối chiếu từng nghiệm ứng viên với điều kiện xác định và phương trình ban đầu.",
        before_latex=sp.latex(problem.relation) if problem.relation is not None else None,
        after_latex=rf"{sp.latex(problem.variable)}\in\left\{{{candidates}\right\}}",
        pitfall="Không kết luận ngay sau khi giải phương trình đã biến đổi; phải thay ngược vào đề gốc.",
        check="Nghiệm hợp lệ không làm mẫu bằng 0, không làm căn/log sai điều kiện và khiến hai vế bằng nhau.",
        result="; ".join(sp.sstr(value) for value in values) if values else "Không còn nghiệm hợp lệ",
        result_latex=rf"\left\{{{candidates}\right\}}",
        kind="verify",
        confidence="verified",
    )


def _verification_step(index: int, status: str, values: list[sp.Expr] | None, solution_set: sp.Set, problem: ParsedAlgebraProblem, expression: sp.Expr) -> AlgebraSolveStep:
    if values is None:
        result_latex = sp.latex(solution_set)
        result = sp.sstr(solution_set)
        explanation = "Tập nghiệm ở dạng biểu thức tập, nên kiểm tra bằng điều kiện mô tả tập nghiệm."
        operation = "Đối chiếu tập nghiệm với phương trình ban đầu."
        check = "Đọc cảnh báo nếu tập nghiệm không hữu hạn hoặc chưa thể thay từng nghiệm cụ thể."
    else:
        result_latex = _substitution_check_latex(problem, expression, values)
        result = "; ".join(sp.sstr(value) for value in values) if values else "Không có nghiệm hữu hạn"
        explanation = "Thay lại từng nghiệm vào phương trình ban đầu để chắc chắn không có nghiệm ngoại lai."
        operation = "Thay nghiệm vào phương trình gốc."
        check = "Mỗi nghiệm phải làm hai vế bằng nhau và thỏa điều kiện xác định."
    confidence = "verified" if status == "verified" else "symbolic" if status == "partially_verified" else "unverified"
    return AlgebraSolveStep(
        index=index,
        title="Thử lại nghiệm",
        explanation=explanation,
        goal="Xác nhận nghiệm tìm được đúng với đề bài gốc.",
        why="Bước kiểm tra giúp phát hiện nghiệm ngoại lai hoặc lỗi do điều kiện xác định.",
        rule="Thay ngược nghiệm",
        operation=operation,
        after_latex=result_latex,
        pitfall="Nếu một nghiệm không qua bước thay ngược, không được giữ trong tập nghiệm.",
        check=check,
        result=result,
        result_latex=result_latex,
        kind="verify",
        confidence=confidence,
    )


def _substitution_check_latex(problem: ParsedAlgebraProblem, expression: sp.Expr, values: list[sp.Expr]) -> str:
    if not values:
        return r"S=\varnothing"
    variable_latex = sp.latex(problem.variable)
    expression_latex = sp.latex(expression)
    lines: list[str] = []
    for value in values[:4]:
        value_latex = sp.latex(value)
        substituted = expression_latex.replace(variable_latex, rf"\left({value_latex}\right)")
        simplified = sp.simplify(expression.subs(problem.variable, value))
        lines.append(rf"{variable_latex}={value_latex}:\quad {substituted}={sp.latex(simplified)}")
    if len(values) > 4:
        lines.append(r"\ldots")
    return r"\begin{aligned}" + r"\\".join(lines) + r"\end{aligned}"


def _display_answer(expression: sp.Expr, variable: sp.Symbol, solution_set: sp.Set, values: list[sp.Expr] | None) -> tuple[str, str | None]:
    if values is not None and _polynomial_degree(expression, variable) is not None and (_polynomial_degree(expression, variable) or 0) >= 3:
        approximate_values = [sp.N(value, 8) for value in values]
        answer = "Tập nghiệm xấp xỉ: {" + "; ".join(sp.sstr(value) for value in approximate_values) + "}"
        answer_latex = r"S \approx \left\{" + ", ".join(sp.latex(value) for value in approximate_values) + r"\right\}"
        return answer, answer_latex
    return format_solution_set(solution_set), sp.latex(solution_set)


def _polynomial_degree(expression: sp.Expr, variable: sp.Symbol) -> int | None:
    try:
        return sp.Poly(sp.expand(expression), variable).degree()
    except sp.PolynomialError:
        return None


def _factor_steps(expression: sp.Expr, variable: sp.Symbol, start_index: int) -> list[AlgebraSolveStep]:
    try:
        polynomial = sp.Poly(sp.expand(expression), variable)
    except sp.PolynomialError:
        return []
    if polynomial.degree() < 2:
        return []
    factored = sp.factor(polynomial.as_expr())
    if sp.expand(factored) == factored:
        return []
    factor_data = [(base, power) for base, power in sp.factor_list(polynomial.as_expr())[1] if base.has(variable)]
    if not factor_data:
        return []
    all_linear = True
    factor_equations: list[str] = []
    factor_equations_latex: list[str] = []
    roots: list[sp.Expr] = []
    for base, _power in factor_data:
        try:
            factor_poly = sp.Poly(base, variable)
        except sp.PolynomialError:
            all_linear = False
            continue
        if factor_poly.degree() != 1:
            all_linear = False
            continue
        root = sp.solve(sp.Eq(base, 0), variable)
        if not root:
            all_linear = False
            continue
        roots.append(sp.simplify(root[0]))
        factor_equations.append(f"{sp.sstr(base)}=0")
        factor_equations_latex.append(sp.latex(sp.Eq(base, 0, evaluate=False)))
    steps = [
        AlgebraSolveStep(
            index=start_index,
            title="Phân tích nhân tử",
            explanation="Ta phân tích vế trái thành tích để dùng quy tắc tích bằng 0.",
            goal="Biến một phương trình đa thức thành các phương trình nhỏ hơn.",
            why="Nếu tích các nhân tử bằng 0 thì ít nhất một nhân tử phải bằng 0.",
            rule="Đặt nhân tử chung và phân tích nhân tử",
            operation="Tìm nhân tử chung hoặc tách đa thức thành tích các nhân tử.",
            before_latex=sp.latex(sp.Eq(polynomial.as_expr(), 0, evaluate=False)),
            after_latex=sp.latex(sp.Eq(factored, 0, evaluate=False)),
            pitfall="Chỉ được dùng quy tắc tích bằng 0 khi vế phải là 0.",
            check="Khai triển tích sau phân tích phải thu lại đúng đa thức ban đầu.",
            expression=sp.sstr(polynomial.as_expr()),
            expression_latex=sp.latex(sp.Eq(polynomial.as_expr(), 0, evaluate=False)),
            result=sp.sstr(factored),
            result_latex=sp.latex(sp.Eq(factored, 0, evaluate=False)),
            kind="transform",
            confidence="symbolic",
        )
    ]
    if all_linear and roots:
        roots = sorted(set(roots), key=sp.default_sort_key)
        factor_equations_joined = r"\;\text{hoặc}\;".join(factor_equations_latex)
        roots_joined = r"\;\text{hoặc}\;".join(rf"{sp.latex(variable)}={sp.latex(root)}" for root in roots)
        steps.append(AlgebraSolveStep(
            index=start_index + 1,
            title="Cho từng nhân tử bằng 0",
            explanation="Vì tích bằng 0 nên cho từng nhân tử bằng 0 rồi giải.",
            goal="Tìm nghiệm của phương trình sau khi đã phân tích nhân tử.",
            why="Một tích bằng 0 khi có ít nhất một thừa số bằng 0.",
            rule="Quy tắc tích bằng 0",
            operation="Giải lần lượt " + "; ".join(factor_equations) + ".",
            before_latex=sp.latex(sp.Eq(factored, 0, evaluate=False)),
            after_latex=rf"{factor_equations_joined}" + "\n" + rf"\Rightarrow {roots_joined}",
            pitfall="Không bỏ sót nhân tử lặp; nhân tử lặp vẫn cho cùng một nghiệm.",
            check="Thay từng nghiệm vào tích đã phân tích để thấy một nhân tử bằng 0.",
            expression="; ".join(factor_equations),
            expression_latex=r"\quad;\quad ".join(factor_equations_latex),
            result="; ".join(sp.sstr(root) for root in roots),
            result_latex=r"\left\{" + ", ".join(sp.latex(root) for root in roots) + r"\right\}",
            kind="solve",
            confidence="symbolic",
        ))
    return steps


def _depressed_cubic_steps(expression: sp.Expr, variable: sp.Symbol, start_index: int) -> list[AlgebraSolveStep]:
    try:
        polynomial = sp.Poly(sp.expand(expression), variable)
    except sp.PolynomialError:
        return []
    if polynomial.degree() != 3:
        return []

    a, b, c, d = polynomial.all_coeffs()
    if sp.simplify(b) != 0:
        return []

    p = sp.simplify(c / a)
    q = sp.simplify(d / a)
    discriminant = sp.simplify((q / 2) ** 2 + (p / 3) ** 3)
    if not discriminant.is_positive:
        return []

    left_radical = sp.simplify(-q / 2 + sp.sqrt(discriminant))
    right_radical = sp.simplify(-q / 2 - sp.sqrt(discriminant))
    real_roots = [
        root
        for root in sp.nroots(polynomial.as_expr())
        if abs(sp.im(root)) < 1e-10
    ]
    approximate_root = sp.N(sp.re(real_roots[0]), 8) if real_roots else None
    approximate_latex = f"\\approx {sp.latex(approximate_root)}" if approximate_root is not None else ""

    return [
        AlgebraSolveStep(
            index=start_index,
            title="Đưa về dạng bậc ba Cardano",
            explanation="Phương trình có dạng x^3 + px + q = 0 nên có thể dùng công thức Cardano.",
            goal="Nhận dạng dạng bậc ba đặc biệt để chọn phương pháp giải phù hợp.",
            why="Khi hệ số bậc hai bằng 0, phương trình bậc ba có thể viết thành x^3 + px + q = 0.",
            rule="Dạng Cardano rút gọn",
            operation="Chia các hệ số cho hệ số bậc ba và đọc p, q.",
            before_latex=sp.latex(sp.Eq(expression, 0, evaluate=False)),
            after_latex=sp.latex(sp.Eq(polynomial.as_expr(), 0, evaluate=False)),
            pitfall="Chỉ dùng bước này cho dạng bậc ba đã khuyết hạng tử bậc hai.",
            check="Sau khi chuẩn hóa, hệ số của x^3 phải là 1 và không còn hạng tử x^2.",
            expression=sp.sstr(polynomial.as_expr()),
            expression_latex=sp.latex(sp.Eq(polynomial.as_expr(), 0, evaluate=False)),
            result=f"p={sp.sstr(p)}, q={sp.sstr(q)}",
            result_latex=rf"p={sp.latex(p)},\quad q={sp.latex(q)}",
            kind="transform",
            confidence="symbolic",
        ),
        AlgebraSolveStep(
            index=start_index + 1,
            title="Tính biệt thức Cardano",
            explanation="Tính D = (q/2)^2 + (p/3)^3. Với D > 0, phương trình có một nghiệm thực.",
            goal="Xác định cấu trúc nghiệm của phương trình bậc ba rút gọn.",
            why="Biệt thức Cardano cho biết công thức nghiệm thực sẽ dùng hai căn bậc ba thực.",
            rule="Biệt thức Cardano",
            operation="Thay p và q vào D = (q/2)^2 + (p/3)^3.",
            before_latex=rf"D=\left(\frac{{q}}{{2}}\right)^2+\left(\frac{{p}}{{3}}\right)^3",
            after_latex=rf"D={sp.latex(discriminant)}",
            pitfall="Không nhầm biệt thức Cardano với Delta của phương trình bậc hai.",
            check="D > 0 nghĩa là trong miền thực có một nghiệm thực.",
            expression="D = (q/2)^2 + (p/3)^3",
            expression_latex=rf"D=\left(\frac{{q}}{{2}}\right)^2+\left(\frac{{p}}{{3}}\right)^3",
            result=sp.sstr(discriminant),
            result_latex=rf"D=\left(\frac{{{sp.latex(q)}}}{{2}}\right)^2+\left(\frac{{{sp.latex(p)}}}{{3}}\right)^3={sp.latex(discriminant)}>0",
            kind="transform",
            confidence="symbolic",
        ),
        AlgebraSolveStep(
            index=start_index + 2,
            title="Áp dụng công thức Cardano",
            explanation="Nghiệm thực được tính bằng tổng hai căn bậc ba.",
            goal="Tính nghiệm thực từ p, q và D.",
            why="Với dạng x^3 + px + q = 0 và D > 0, công thức Cardano cho trực tiếp nghiệm thực.",
            rule="Công thức Cardano",
            operation="Thay p, q, D vào tổng hai căn bậc ba rồi lấy giá trị gần đúng.",
            before_latex=rf"{sp.latex(variable)}=\sqrt[3]{{-\frac{{q}}{{2}}+\sqrt{{D}}}}+\sqrt[3]{{-\frac{{q}}{{2}}-\sqrt{{D}}}}",
            after_latex=rf"{sp.latex(variable)}=\sqrt[3]{{{sp.latex(left_radical)}}}+\sqrt[3]{{{sp.latex(right_radical)}}}{approximate_latex}",
            pitfall="Căn bậc ba có thể nhận giá trị âm; không xử lý như căn bậc hai.",
            check="Thay nghiệm gần đúng vào phương trình gốc để kiểm tra sai số nhỏ.",
            expression=f"{sp.sstr(variable)} = cbrt(-q/2 + sqrt(D)) + cbrt(-q/2 - sqrt(D))",
            expression_latex=rf"{sp.latex(variable)}=\sqrt[3]{{-\frac{{q}}{{2}}+\sqrt{{D}}}}+\sqrt[3]{{-\frac{{q}}{{2}}-\sqrt{{D}}}}",
            result=sp.sstr(approximate_root) if approximate_root is not None else "",
            result_latex=rf"{sp.latex(variable)}=\sqrt[3]{{{sp.latex(left_radical)}}}+\sqrt[3]{{{sp.latex(right_radical)}}}{approximate_latex}",
            kind="solve",
            confidence="symbolic",
        ),
    ]


def _quadratic_steps(expression: sp.Expr, variable: sp.Symbol, start_index: int) -> list[AlgebraSolveStep]:
    try:
        polynomial = sp.Poly(sp.expand(expression), variable)
    except sp.PolynomialError:
        return []
    if polynomial.degree() != 2:
        return []

    a, b, c = polynomial.all_coeffs()
    delta = sp.simplify(b**2 - 4 * a * c)
    standard_expression = sp.expand(a * variable**2 + b * variable + c)
    steps = [
        AlgebraSolveStep(
            index=start_index,
            title="Đưa về dạng chuẩn bậc hai",
            explanation="Chuyển phương trình về dạng ax^2 + bx + c = 0 và đọc các hệ số.",
            goal="Đưa phương trình về dạng chuẩn để dùng công thức nghiệm.",
            why="Công thức nghiệm bậc hai chỉ áp dụng trực tiếp cho ax^2 + bx + c = 0 với a khác 0.",
            rule="Dạng chuẩn bậc hai",
            operation="Rút gọn biểu thức một vế và đọc hệ số a, b, c theo thứ tự bậc giảm dần.",
            before_latex=sp.latex(sp.Eq(expression, 0, evaluate=False)),
            after_latex=sp.latex(sp.Eq(standard_expression, 0, evaluate=False)),
            pitfall="Phải giữ cả dấu âm của hệ số; sai dấu b hoặc c sẽ làm Delta sai.",
            check="Biểu thức sau khi khai triển phải đúng với phương trình một vế ban đầu.",
            expression=sp.sstr(standard_expression),
            expression_latex=sp.latex(sp.Eq(standard_expression, 0, evaluate=False)),
            result=f"a={sp.sstr(a)}, b={sp.sstr(b)}, c={sp.sstr(c)}",
            result_latex=rf"a={sp.latex(a)},\quad b={sp.latex(b)},\quad c={sp.latex(c)}",
            kind="transform",
            confidence="symbolic",
        ),
        AlgebraSolveStep(
            index=start_index + 1,
            title="Tính biệt thức",
            explanation="Dùng biệt thức Delta = b^2 - 4ac để xác định số nghiệm thực.",
            goal="Quyết định phương trình có bao nhiêu nghiệm thực.",
            why="Dấu của Delta cho biết phương trình bậc hai có hai nghiệm, một nghiệm kép hay vô nghiệm trên R.",
            rule="Biệt thức Delta",
            operation="Thay hệ số a, b, c vào Delta = b^2 - 4ac.",
            before_latex=rf"\Delta=b^2-4ac",
            after_latex=rf"\Delta={sp.latex(delta)}",
            pitfall="Cẩn thận với b^2: nếu b âm thì bình phương vẫn dương.",
            check="Nếu Delta > 0 có hai nghiệm; Delta = 0 có nghiệm kép; Delta < 0 vô nghiệm trên R.",
            expression="Delta = b^2 - 4*a*c",
            expression_latex=rf"\Delta=b^2-4ac",
            result=sp.sstr(delta),
            result_latex=rf"\Delta=\left({sp.latex(b)}\right)^2-4\cdot {sp.latex(a)}\cdot \left({sp.latex(c)}\right)={sp.latex(delta)}",
            kind="transform",
            confidence="symbolic",
        ),
    ]

    root_step = _quadratic_root_step(a, b, delta, variable, start_index + 2)
    if root_step:
        steps.append(root_step)
    return steps


def _quadratic_root_step(a: sp.Expr, b: sp.Expr, delta: sp.Expr, variable: sp.Symbol, index: int) -> AlgebraSolveStep | None:
    if sp.simplify(delta) == 0:
        root = sp.simplify(-b / (2 * a))
        return AlgebraSolveStep(
            index=index,
            title="Tính nghiệm kép",
            explanation="Vì Delta = 0, phương trình có một nghiệm kép.",
            goal="Tìm nghiệm kép của phương trình bậc hai.",
            why="Khi Delta bằng 0, hai nghiệm trong công thức nghiệm trùng nhau.",
            rule="Nghiệm kép bậc hai",
            operation="Thay a và b vào x = -b/(2a).",
            before_latex=rf"{sp.latex(variable)}=\frac{{-b}}{{2a}}",
            after_latex=rf"{sp.latex(variable)}={sp.latex(root)}",
            pitfall="Không viết hai nghiệm khác nhau khi Delta bằng 0.",
            check="Thay nghiệm kép vào phương trình gốc để xác nhận vế trái bằng vế phải.",
            expression=sp.sstr(root),
            expression_latex=rf"{sp.latex(variable)}=\frac{{-b}}{{2a}}",
            result=sp.sstr(root),
            result_latex=rf"{sp.latex(variable)}=\frac{{-\left({sp.latex(b)}\right)}}{{2\cdot {sp.latex(a)}}}={sp.latex(root)}",
            kind="solve",
            confidence="symbolic",
        )

    if delta.is_negative:
        return AlgebraSolveStep(
            index=index,
            title="Kết luận theo biệt thức",
            explanation="Vì Delta < 0, phương trình không có nghiệm thực.",
            goal="Loại trường hợp có nghiệm thực.",
            why="Trong miền số thực, căn bậc hai của Delta âm không tồn tại.",
            rule="Delta âm",
            operation="Dùng dấu của Delta để kết luận tập nghiệm thực rỗng.",
            before_latex=rf"\Delta={sp.latex(delta)}",
            after_latex=r"S=\varnothing",
            pitfall="Nếu miền nghiệm là C thì Delta âm vẫn có nghiệm phức; kết luận này dành cho R.",
            check="Đối chiếu miền nghiệm đang chọn trước khi kết luận vô nghiệm.",
            expression=sp.sstr(delta),
            expression_latex=rf"\Delta={sp.latex(delta)}<0",
            result="Vô nghiệm trên R",
            result_latex=r"S=\varnothing",
            kind="solve",
            confidence="symbolic",
        )

    root_1 = sp.simplify((-b - sp.sqrt(delta)) / (2 * a))
    root_2 = sp.simplify((-b + sp.sqrt(delta)) / (2 * a))
    return AlgebraSolveStep(
        index=index,
        title="Áp dụng công thức nghiệm",
        explanation="Vì Delta > 0, phương trình có hai nghiệm phân biệt theo công thức nghiệm bậc hai.",
        goal="Tính hai nghiệm phân biệt của phương trình.",
        why="Delta dương nên căn Delta xác định trong R và tạo ra hai giá trị với dấu cộng/trừ.",
        rule="Công thức nghiệm bậc hai",
        operation="Thay a, b và Delta vào x = (-b ± sqrt(Delta))/(2a).",
        before_latex=rf"{sp.latex(variable)}=\frac{{-b\pm\sqrt{{\Delta}}}}{{2a}}",
        after_latex=rf"{sp.latex(variable)}_1={sp.latex(root_1)},\quad {sp.latex(variable)}_2={sp.latex(root_2)}",
        pitfall="Mẫu số là 2a, không phải 2; đồng thời phải tính cả nhánh dấu trừ và dấu cộng.",
        check="Thay từng nghiệm vào phương trình gốc để cả hai vế bằng nhau.",
        expression=f"{sp.sstr(variable)} = (-b ± sqrt(Delta))/(2*a)",
        expression_latex=rf"{sp.latex(variable)}=\frac{{-b\pm\sqrt{{\Delta}}}}{{2a}}",
        result=f"{sp.sstr(root_1)}; {sp.sstr(root_2)}",
        result_latex=rf"{sp.latex(variable)}_1=\frac{{-\left({sp.latex(b)}\right)-\sqrt{{{sp.latex(delta)}}}}}{{2\cdot {sp.latex(a)}}}={sp.latex(root_1)},\quad {sp.latex(variable)}_2=\frac{{-\left({sp.latex(b)}\right)+\sqrt{{{sp.latex(delta)}}}}}{{2\cdot {sp.latex(a)}}}={sp.latex(root_2)}",
        kind="solve",
        confidence="symbolic",
    )
