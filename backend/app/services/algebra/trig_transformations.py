from __future__ import annotations

import sympy as sp

from app.schemas.algebra import AlgebraSolveStep
from app.services.algebra.parser import ParsedAlgebraProblem

TRIG_FUNCTIONS = (sp.sin, sp.cos, sp.tan, sp.cot)


def trig_domain_assumptions(expression: sp.Expr, variable: sp.Symbol) -> list[str]:
    assumptions: list[str] = []
    for tan_expr in expression.atoms(sp.tan):
        arg = tan_expr.args[0]
        if arg.has(variable):
            assumptions.append(f"cos({sp.sstr(arg)}) khác 0")
    for cot_expr in expression.atoms(sp.cot):
        arg = cot_expr.args[0]
        if arg.has(variable):
            assumptions.append(f"sin({sp.sstr(arg)}) khác 0")
    return _unique(assumptions)


def build_trig_steps(problem: ParsedAlgebraProblem, expression: sp.Expr, solution_set: sp.Set, values: list[sp.Expr] | None, start_index: int) -> list[AlgebraSolveStep]:
    return (
        _identity_steps(problem, expression, solution_set, start_index)
        or _quadratic_single_function_steps(problem, expression, solution_set, values, start_index)
        or _linear_sin_cos_steps(problem, expression, solution_set, values, start_index)
        or _sum_to_product_steps(problem, expression, solution_set, values, start_index)
        or _double_angle_steps(problem, expression, solution_set, values, start_index)
        or _product_steps(problem, expression, solution_set, values, start_index)
        or _basic_trig_steps(problem, expression, solution_set, values, start_index)
    )


def _identity_steps(problem: ParsedAlgebraProblem, expression: sp.Expr, solution_set: sp.Set, start_index: int) -> list[AlgebraSolveStep]:
    simplified = sp.trigsimp(expression)
    if simplified != 0:
        return []
    return [
        AlgebraSolveStep(
            index=start_index,
            title="Rút gọn bằng đồng nhất thức lượng giác",
            explanation="Vế trái trừ vế phải rút gọn về 0 nhờ đồng nhất thức lượng giác.",
            short_explanation="Dùng đồng nhất thức để rút gọn phương trình về đúng với mọi x trong miền xét.",
            detail_level="brief",
            method="trig_identity_simplify",
            goal="Nhận ra phương trình đúng hiển nhiên sau khi rút gọn.",
            why="Các đồng nhất thức như sin^2(x)+cos^2(x)=1 giúp rút gọn toàn bộ biểu thức.",
            rule="Đồng nhất thức lượng giác",
            operation="Rút gọn vế trái trừ vế phải bằng trigsimp.",
            before_latex=sp.latex(problem.relation),
            after_latex=sp.latex(sp.Eq(0, 0, evaluate=False)),
            pitfall="Vẫn phải giữ điều kiện xác định nếu có tan, cot hoặc mẫu lượng giác.",
            check="Thay vài giá trị trong miền xác định sẽ luôn làm phương trình đúng.",
            result=sp.sstr(solution_set),
            result_latex=sp.latex(solution_set),
            kind="transform",
            confidence="symbolic",
        )
    ]


def _quadratic_single_function_steps(problem: ParsedAlgebraProblem, expression: sp.Expr, solution_set: sp.Set, values: list[sp.Expr] | None, start_index: int) -> list[AlgebraSolveStep]:
    variable = problem.variable
    for func in (sp.sin, sp.cos, sp.tan):
        t = sp.Symbol("t", real=True)
        unit = func(variable)
        rewritten = sp.expand(expression.xreplace({unit: t}))
        if rewritten.has(func):
            continue
        try:
            poly = sp.Poly(rewritten, t)
        except sp.PolynomialError:
            continue
        if poly.degree() < 2:
            continue
        roots = sorted(sp.solve(sp.Eq(poly.as_expr(), 0), t), key=sp.default_sort_key)
        valid_roots = [root for root in roots if func is sp.tan or _in_unit_range(root)]
        lines = [sp.latex(sp.Eq(func(variable), root, evaluate=False)) for root in valid_roots]
        return [
            AlgebraSolveStep(
                index=start_index,
                title=f"Đặt ẩn phụ t = {func.__name__}(x)",
                explanation=f"Phương trình là bậc hai theo {func.__name__}(x), nên đặt t = {func.__name__}(x).",
                short_explanation=f"Đặt t = {func.__name__}(x) để đưa về phương trình đại số.",
                detail_level="brief",
                method="trig_substitution",
                goal="Đưa phương trình lượng giác về phương trình theo t.",
                why="Khi chỉ xuất hiện một hàm lượng giác và các lũy thừa của nó, đặt ẩn phụ làm bài toán đơn giản hơn.",
                rule="Đặt ẩn phụ lượng giác",
                operation=f"Thay {func.__name__}(x) bằng t.",
                before_latex=sp.latex(problem.relation),
                after_latex=rf"t={sp.latex(func(variable))}" + "\n" + sp.latex(sp.Eq(poly.as_expr(), 0, evaluate=False)),
                pitfall="Với sin/cos phải lọc -1 <= t <= 1.",
                check="Thay t ngược lại phải thu được phương trình ban đầu.",
                result=sp.sstr(poly.as_expr()),
                result_latex=sp.latex(sp.Eq(poly.as_expr(), 0, evaluate=False)),
                kind="transform",
                confidence="symbolic",
            ),
            AlgebraSolveStep(
                index=start_index + 1,
                title="Giải phương trình theo ẩn phụ",
                explanation="Giải phương trình đại số theo t và giữ các giá trị t hợp lệ.",
                short_explanation="Giải theo t rồi lọc điều kiện của sin/cos/tan.",
                detail_level="standard",
                method="solve_trig_substitution",
                goal="Tìm các giá trị lượng giác cần đạt.",
                why="Sau khi đặt ẩn phụ, bài toán trở thành phương trình đại số.",
                rule="Giải phương trình theo t",
                operation="Giải phương trình rồi đổi ngược về hàm lượng giác.",
                before_latex=sp.latex(sp.Eq(poly.as_expr(), 0, evaluate=False)),
                after_latex="\n".join(lines),
                pitfall="Không dùng nghiệm t ngoài [-1,1] cho sin/cos.",
                check="Mỗi giá trị t giữ lại phải nằm trong miền giá trị của hàm.",
                result="; ".join(sp.sstr(root) for root in valid_roots),
                result_latex="\n".join(lines),
                kind="solve",
                confidence="symbolic",
            ),
            _filter_interval_step(start_index + 2, solution_set, values),
        ]
    return []


def _linear_sin_cos_steps(problem: ParsedAlgebraProblem, expression: sp.Expr, solution_set: sp.Set, values: list[sp.Expr] | None, start_index: int) -> list[AlgebraSolveStep]:
    variable = problem.variable
    expanded = sp.expand(expression)
    a = expanded.coeff(sp.sin(variable))
    b = expanded.coeff(sp.cos(variable))
    constant = sp.simplify(expanded - a * sp.sin(variable) - b * sp.cos(variable))
    if a == 0 or b == 0 or constant.has(variable):
        return []
    rhs = sp.simplify(-constant)
    radius = sp.sqrt(a ** 2 + b ** 2)
    phi = sp.atan2(b, a)
    return [
        AlgebraSolveStep(
            index=start_index,
            title="Đưa về dạng R·sin(x+phi)",
            explanation="Tổ hợp a·sin(x)+b·cos(x) được viết thành R·sin(x+phi).",
            short_explanation="Gom a·sin(x)+b·cos(x) thành một hàm sin lệch pha.",
            detail_level="brief",
            method="asin_bcos",
            goal="Đưa phương trình về phương trình lượng giác cơ bản.",
            why="Dạng R·sin(x+phi)=c dễ giải hơn tổng sin và cos.",
            rule="a sin x + b cos x = R sin(x+phi)",
            operation="Tính R=sqrt(a^2+b^2), chọn cos(phi)=a/R và sin(phi)=b/R.",
            before_latex=sp.latex(problem.relation),
            after_latex=sp.latex(sp.Eq(radius * sp.sin(variable + phi), rhs, evaluate=False)),
            pitfall="Phương trình chỉ có nghiệm nếu |c| <= R.",
            check="Khai triển R·sin(x+phi) phải ra lại a·sin(x)+b·cos(x).",
            result_latex=sp.latex(sp.Eq(radius * sp.sin(variable + phi), rhs, evaluate=False)),
            kind="transform",
            confidence="symbolic",
        ),
        _filter_interval_step(start_index + 1, solution_set, values),
    ]


def _product_steps(problem: ParsedAlgebraProblem, expression: sp.Expr, solution_set: sp.Set, values: list[sp.Expr] | None, start_index: int) -> list[AlgebraSolveStep]:
    factored = sp.factor(sp.expand_trig(expression))
    if not isinstance(factored, sp.Mul) or not factored.has(*TRIG_FUNCTIONS):
        return []
    factors = [factor for factor in sp.Mul.make_args(factored) if factor.has(*TRIG_FUNCTIONS)]
    if len(factors) < 2:
        return []
    factor_lines = [sp.latex(sp.Eq(factor, 0, evaluate=False)) for factor in factors]
    return [
        AlgebraSolveStep(
            index=start_index,
            title="Đưa về tích các nhân tử lượng giác",
            explanation="Biến đổi phương trình về dạng tích bằng 0 để giải từng nhân tử.",
            short_explanation="Phân tích thành tích rồi cho từng nhân tử bằng 0.",
            detail_level="brief",
            method="trig_product_zero",
            goal="Tách phương trình lượng giác thành các phương trình nhỏ hơn.",
            why="Nếu một tích bằng 0 thì ít nhất một nhân tử bằng 0.",
            rule="Tích bằng 0",
            operation="Phân tích nhân tử sau khi dùng công thức lượng giác cần thiết.",
            before_latex=sp.latex(problem.relation),
            after_latex=sp.latex(sp.Eq(factored, 0, evaluate=False)),
            pitfall="Chỉ dùng quy tắc tích bằng 0 khi vế phải là 0.",
            check="Khai triển tích phải thu lại phương trình đã biến đổi.",
            result_latex=sp.latex(sp.Eq(factored, 0, evaluate=False)),
            kind="transform",
            confidence="symbolic",
        ),
        AlgebraSolveStep(
            index=start_index + 1,
            title="Cho từng nhân tử bằng 0",
            explanation="Giải lần lượt từng phương trình lượng giác cơ bản thu được.",
            short_explanation="Giải từng nhân tử lượng giác.",
            detail_level="standard",
            method="solve_trig_factors",
            goal="Tìm nghiệm từ từng nhân tử.",
            why="Mỗi nhân tử bằng 0 tạo ra một họ nghiệm.",
            rule="Quy tắc tích bằng 0",
            operation="Cho từng nhân tử bằng 0 rồi lọc nghiệm trên khoảng chuẩn.",
            before_latex=sp.latex(sp.Eq(factored, 0, evaluate=False)),
            after_latex="\n".join(factor_lines),
            pitfall="Không bỏ sót nghiệm trùng giữa các nhân tử.",
            check="Hợp các nghiệm của từng nhân tử phải thỏa phương trình gốc.",
            result_latex="\n".join(factor_lines),
            kind="solve",
            confidence="symbolic",
        ),
        _filter_interval_step(start_index + 2, solution_set, values),
    ]


def _sum_to_product_steps(problem: ParsedAlgebraProblem, expression: sp.Expr, solution_set: sp.Set, values: list[sp.Expr] | None, start_index: int) -> list[AlgebraSolveStep]:
    variable = problem.variable
    terms = sp.Add.make_args(sp.expand(expression))
    sine_terms = [term for term in terms if term.func is sp.sin and term.args[0].has(variable)]
    if len(sine_terms) != 2 or len(terms) != 2:
        return []
    a, b = sine_terms[0].args[0], sine_terms[1].args[0]
    transformed = 2 * sp.sin((a + b) / 2) * sp.cos((a - b) / 2)
    return [
        AlgebraSolveStep(
            index=start_index,
            title="Dùng công thức tổng thành tích",
            explanation="Tổng hai sin được đổi thành tích để dùng quy tắc tích bằng 0.",
            short_explanation="Đổi tổng sin thành tích.",
            detail_level="brief",
            method="sum_to_product",
            goal="Đưa phương trình về dạng tích.",
            why="Dạng tích dễ giải vì có thể cho từng nhân tử bằng 0.",
            rule="sin A + sin B = 2sin((A+B)/2)cos((A-B)/2)",
            operation="Áp dụng công thức tổng thành tích.",
            before_latex=sp.latex(problem.relation),
            after_latex=sp.latex(sp.Eq(transformed, 0, evaluate=False)),
            pitfall="Phải chia đôi đúng tổng và hiệu của hai góc.",
            check="Khai triển ngược tích phải ra tổng ban đầu.",
            result_latex=sp.latex(sp.Eq(transformed, 0, evaluate=False)),
            kind="transform",
            confidence="symbolic",
        ),
        _filter_interval_step(start_index + 1, solution_set, values),
    ]


def _double_angle_steps(problem: ParsedAlgebraProblem, expression: sp.Expr, solution_set: sp.Set, values: list[sp.Expr] | None, start_index: int) -> list[AlgebraSolveStep]:
    variable = problem.variable
    has_double = expression.has(sp.sin(2 * variable), sp.cos(2 * variable), sp.tan(2 * variable), sp.cot(2 * variable))
    expanded = sp.expand_trig(expression)
    if not has_double or expanded == expression:
        return []
    factored = sp.factor(expanded)
    return [
        AlgebraSolveStep(
            index=start_index,
            title="Dùng công thức góc đôi",
            explanation="Biến đổi sin(2x), cos(2x) hoặc tan(2x) về các hàm của x.",
            short_explanation="Dùng công thức góc đôi để đưa về cùng góc x.",
            detail_level="brief",
            method="double_angle",
            goal="Đưa phương trình về các hàm lượng giác cùng góc.",
            why="Khi các góc khác nhau, công thức góc đôi giúp đưa về một biến lượng giác quen thuộc.",
            rule="Công thức góc đôi",
            operation="Khai triển lượng giác rồi rút gọn/phân tích.",
            before_latex=sp.latex(problem.relation),
            after_latex=sp.latex(sp.Eq(factored, 0, evaluate=False)),
            pitfall="Sau khi biến đổi có thể cần phân tích nhân tử hoặc đặt ẩn phụ.",
            check="Khai triển công thức góc đôi phải tương đương phương trình ban đầu.",
            result_latex=sp.latex(sp.Eq(factored, 0, evaluate=False)),
            kind="transform",
            confidence="symbolic",
        ),
        _filter_interval_step(start_index + 1, solution_set, values),
    ]


def _basic_trig_steps(problem: ParsedAlgebraProblem, expression: sp.Expr, solution_set: sp.Set, values: list[sp.Expr] | None, start_index: int) -> list[AlgebraSolveStep]:
    parsed = _basic_trig_relation(problem)
    if parsed is None:
        return []
    func, argument, target = parsed
    function_name = func.__name__
    general_latex = _basic_trig_general_latex(func, argument, target)
    steps = [
        AlgebraSolveStep(
            index=start_index,
            title="Đưa về phương trình lượng giác cơ bản",
            explanation=f"Nhận dạng phương trình dạng {function_name}(u) = a.",
            short_explanation=f"Đưa về dạng {function_name}(u)=a.",
            detail_level="brief",
            method="basic_trig_equation",
            goal="Tách phần góc và giá trị lượng giác cần đạt.",
            why="Các phương trình lượng giác cơ bản có công thức nghiệm theo chu kỳ.",
            rule="Phương trình lượng giác cơ bản",
            operation="Đặt u bằng biểu thức trong hàm lượng giác.",
            before_latex=sp.latex(problem.relation),
            after_latex=rf"u={sp.latex(argument)}" + "\n" + sp.latex(sp.Eq(func(sp.Symbol("u")), target, evaluate=False)),
            pitfall="Nếu góc là 2x hoặc x+a, phải giải tiếp phương trình theo x.",
            check="Thay u ngược lại phải ra phương trình ban đầu.",
            expression=sp.sstr(expression),
            expression_latex=sp.latex(expression),
            result_latex=sp.latex(sp.Eq(func(argument), target, evaluate=False)),
            kind="transform",
            confidence="symbolic",
        ),
        AlgebraSolveStep(
            index=start_index + 1,
            title="Viết nghiệm theo chu kỳ",
            explanation="Dùng nghiệm cơ bản của hàm lượng giác và chu kỳ để mô tả các nghiệm trên R.",
            short_explanation="Viết nghiệm tổng quát theo chu kỳ.",
            detail_level="standard",
            method="trig_periodic_solution",
            goal="Không bỏ sót nghiệm do tính tuần hoàn.",
            why="Sin, cos, tan lặp lại giá trị theo chu kỳ nên thường có nhiều nghiệm.",
            rule="Chu kỳ lượng giác",
            operation="Viết nghiệm tổng quát với tham số k ∈ Z.",
            before_latex=sp.latex(sp.Eq(func(argument), target, evaluate=False)),
            after_latex=general_latex,
            pitfall="Không chỉ lấy một góc đặc biệt khi còn nghiệm đối xứng hoặc nghiệm theo chu kỳ.",
            check="Các nghiệm đại diện phải cho đúng giá trị lượng giác ban đầu.",
            result_latex=general_latex,
            kind="solve",
            confidence="symbolic",
        ),
        _filter_interval_step(start_index + 2, solution_set, values),
    ]
    return steps


def _basic_trig_relation(problem: ParsedAlgebraProblem) -> tuple[object, sp.Expr, sp.Expr] | None:
    if problem.relation is None:
        return None
    lhs, rhs = problem.relation.lhs, problem.relation.rhs
    for func in TRIG_FUNCTIONS:
        if lhs.func is func and not rhs.has(problem.variable):
            return func, lhs.args[0], rhs
        if rhs.func is func and not lhs.has(problem.variable):
            return func, rhs.args[0], lhs
    return None


def _basic_trig_general_latex(func, argument: sp.Expr, target: sp.Expr) -> str:
    k = sp.Symbol("k", integer=True)
    if func is sp.sin:
        alpha = sp.asin(target)
        return "\n".join([
            sp.latex(sp.Eq(argument, alpha + 2 * k * sp.pi, evaluate=False)),
            sp.latex(sp.Eq(argument, sp.pi - alpha + 2 * k * sp.pi, evaluate=False)),
        ])
    if func is sp.cos:
        alpha = sp.acos(target)
        return "\n".join([
            sp.latex(sp.Eq(argument, alpha + 2 * k * sp.pi, evaluate=False)),
            sp.latex(sp.Eq(argument, -alpha + 2 * k * sp.pi, evaluate=False)),
        ])
    if func is sp.tan:
        alpha = sp.atan(target)
        return sp.latex(sp.Eq(argument, alpha + k * sp.pi, evaluate=False))
    return sp.latex(sp.Eq(func(argument), target, evaluate=False))


def _filter_interval_step(index: int, solution_set: sp.Set, values: list[sp.Expr] | None) -> AlgebraSolveStep:
    # Default product path: general solution on R (no silent [0, 2π) truncation).
    if values is None:
        return AlgebraSolveStep(
            index=index,
            title="Nghiệm tổng quát trên R",
            explanation="Trên miền số thực, nghiệm lượng giác được giữ dạng tổng quát theo chu kỳ (k ∈ Z), không cắt còn một chu kỳ [0, 2π).",
            short_explanation="Giữ nghiệm tổng quát trên R.",
            detail_level="standard",
            method="trig_general_solution",
            goal="Trình bày đầy đủ tập nghiệm trên R.",
            why="Nghiệm lượng giác thường vô hạn; cắt khoảng chỉ hợp lệ khi người dùng chỉ định khoảng.",
            rule="Nghiệm tổng quát",
            operation="Biểu diễn tập nghiệm symbolic / ImageSet theo tham số nguyên.",
            after_latex=sp.latex(solution_set),
            pitfall="Không nhầm nghiệm trong một chu kỳ với nghiệm trên toàn R.",
            check="Các đại diện trong họ nghiệm phải thỏa phương trình gốc.",
            result=sp.sstr(solution_set),
            result_latex=sp.latex(solution_set),
            kind="solve",
            confidence="symbolic",
        )
    return AlgebraSolveStep(
        index=index,
        title="Tập nghiệm hữu hạn",
        explanation="Tập nghiệm trên miền đang xét là hữu hạn; liệt kê các giá trị cụ thể.",
        short_explanation="Liệt kê nghiệm hữu hạn.",
        detail_level="standard",
        method="trig_finite_solutions",
        goal="Viết nghiệm cụ thể.",
        why="Một số phương trình lượng giác chỉ có hữu hạn nghiệm trên miền đã chọn.",
        rule="Liệt kê nghiệm",
        operation="Ghi các nghiệm đã tìm được.",
        after_latex=sp.latex(solution_set),
        pitfall="Kiểm tra điều kiện xác định (tan, cot, ...).",
        check="Từng nghiệm phải thỏa phương trình gốc.",
        result="; ".join(sp.sstr(value) for value in values),
        result_latex=sp.latex(solution_set),
        kind="verify",
        confidence="verified",
    )


def _in_unit_range(value: sp.Expr) -> bool:
    try:
        return bool(sp.simplify(value >= -1)) and bool(sp.simplify(value <= 1))
    except Exception:
        return False


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
