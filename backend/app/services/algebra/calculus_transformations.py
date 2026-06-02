from __future__ import annotations

import sympy as sp

from app.schemas.algebra import AlgebraSolveStep


def derivative_steps(expression: sp.Expr, variable: sp.Symbol, derivative: sp.Expr, order: int = 1) -> list[AlgebraSolveStep]:
    if order > 1:
        return _higher_order_derivative_steps(expression, variable, derivative, order)
    return [
        _identify_derivative_step(1, expression, variable),
        _derivative_rule_step(2, expression, variable, derivative),
        _simplify_derivative_step(3, expression, variable, derivative),
    ]


def limit_steps(expression: sp.Expr, variable: sp.Symbol, point: sp.Expr, direction: str, result: sp.Expr) -> list[AlgebraSolveStep]:
    direct = _direct_substitution(expression, variable, point)
    steps = [_direct_limit_step(1, expression, variable, point, direct)]
    technique = (
        _trig_limit_step(len(steps) + 1, expression, variable, point)
        or _conjugate_limit_step(len(steps) + 1, expression, variable, point)
        or _cancel_limit_step(len(steps) + 1, expression, variable, point)
        or _infinity_limit_step(len(steps) + 1, expression, variable, point)
        or _lhospital_step(len(steps) + 1, expression, variable, point)
    )
    if technique:
        steps.append(technique)
    steps.append(AlgebraSolveStep(
        index=len(steps) + 1,
        title="Tính giới hạn sau biến đổi",
        explanation="Tính giới hạn của biểu thức sau khi xử lý dạng cần thiết.",
        short_explanation="Tính giới hạn của biểu thức đã biến đổi.",
        detail_level="standard",
        method="final_limit",
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


def integral_steps(expression: sp.Expr, variable: sp.Symbol, antiderivative: sp.Expr, result: sp.Expr, lower: sp.Expr | None = None, upper: sp.Expr | None = None) -> list[AlgebraSolveStep]:
    steps = [_identify_integral_step(1, expression, variable)]
    technique = (
        _trig_identity_integral_step(2, expression, variable, antiderivative)
        or _partial_fraction_integral_step(2, expression, variable, antiderivative)
        or _u_substitution_integral_step(2, expression, variable, antiderivative)
        or _integration_by_parts_step(2, expression, variable, antiderivative)
        or _basic_integral_step(2, expression, variable, antiderivative)
    )
    steps.append(technique)
    if lower is not None and upper is not None:
        steps.append(_definite_integral_step(len(steps) + 1, variable, antiderivative, result, lower, upper))
    return steps


def _identify_derivative_step(index: int, expression: sp.Expr, variable: sp.Symbol) -> AlgebraSolveStep:
    return AlgebraSolveStep(
        index=index,
        title="Nhận dạng hàm cần đạo hàm",
        explanation="Xác định biểu thức và biến lấy đạo hàm.",
        short_explanation="Xác định f(x) và biến lấy đạo hàm.",
        detail_level="brief",
        method="identify_derivative",
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


def _derivative_rule_step(index: int, expression: sp.Expr, variable: sp.Symbol, derivative: sp.Expr) -> AlgebraSolveStep:
    numerator, denominator = sp.fraction(sp.together(expression))
    if denominator != 1 and denominator.has(variable):
        raw = sp.diff(numerator, variable) * denominator - numerator * sp.diff(denominator, variable)
        return AlgebraSolveStep(
            index=index,
            title="Dùng quy tắc thương",
            explanation="Biểu thức là thương nên dùng quy tắc đạo hàm của thương.",
            short_explanation="Dùng (u/v)' = (u'v - uv')/v^2.",
            detail_level="brief",
            method="quotient_rule",
            goal="Tính đạo hàm của phân thức.",
            why="Không được đạo hàm riêng tử và mẫu rồi chia trực tiếp.",
            rule="(u/v)' = (u'v - uv')/v^2",
            operation="Đặt u là tử, v là mẫu, rồi áp dụng quy tắc thương.",
            before_latex=sp.latex(expression),
            after_latex=sp.latex(raw / denominator ** 2),
            pitfall="Dễ sai dấu ở hạng -u v'.",
            check="Mẫu sau đạo hàm phải là v^2.",
            result_latex=sp.latex(derivative),
            kind="transform",
            confidence="symbolic",
        )
    if isinstance(expression, sp.Pow) and expression.base.has(variable) and expression.exp.has(variable):
        return AlgebraSolveStep(
            index=index,
            title="Dùng đạo hàm logarit",
            explanation="Cơ số và số mũ đều chứa biến nên lấy log hai vế trước khi đạo hàm.",
            short_explanation="Dùng log differentiation cho f(x)^g(x).",
            detail_level="brief",
            method="logarithmic_differentiation",
            goal="Tính đạo hàm dạng u(x)^v(x).",
            why="Dạng này không dùng trực tiếp quy tắc lũy thừa thông thường.",
            rule="ln y = v ln u",
            operation="Đặt y=u^v, lấy ln rồi đạo hàm hai vế.",
            before_latex=sp.latex(expression),
            after_latex=sp.latex(derivative),
            pitfall="Không áp dụng (x^n)' khi số mũ cũng phụ thuộc x.",
            check="Kết quả phải chứa hệ số từ cả cơ số và số mũ.",
            result_latex=sp.latex(derivative),
            kind="transform",
            confidence="symbolic",
        )
    if _is_chain_expression(expression, variable):
        return AlgebraSolveStep(
            index=index,
            title="Dùng quy tắc dây chuyền",
            explanation="Biểu thức là hàm hợp nên lấy đạo hàm hàm ngoài rồi nhân đạo hàm hàm trong.",
            short_explanation="Đạo hàm hàm ngoài, nhân thêm đạo hàm hàm trong.",
            detail_level="brief",
            method="chain_rule",
            goal="Tính đạo hàm hàm hợp.",
            why="Khi f(x)=F(u(x)), cần nhân thêm u'(x).",
            rule="(F(u))' = F'(u)u'",
            operation="Xác định hàm ngoài và hàm trong rồi áp dụng quy tắc dây chuyền.",
            before_latex=sp.latex(expression),
            after_latex=sp.latex(sp.diff(expression, variable)),
            pitfall="Không quên nhân đạo hàm của biểu thức bên trong.",
            check="Nếu u=x thì công thức trở về đạo hàm cơ bản.",
            result_latex=sp.latex(derivative),
            kind="transform",
            confidence="symbolic",
        )
    if expression.is_Mul and len(sp.Mul.make_args(expression)) >= 2:
        return AlgebraSolveStep(
            index=index,
            title="Dùng quy tắc tích",
            explanation="Biểu thức là tích nên dùng quy tắc đạo hàm của tích.",
            short_explanation="Dùng (uv)' = u'v + uv'.",
            detail_level="brief",
            method="product_rule",
            goal="Tính đạo hàm của tích.",
            why="Không được lấy đạo hàm từng thừa số rồi nhân lại.",
            rule="(uv)' = u'v + uv'",
            operation="Áp dụng quy tắc tích rồi rút gọn.",
            before_latex=sp.latex(expression),
            after_latex=sp.latex(sp.diff(expression, variable)),
            pitfall="Sai lầm thường gặp là viết (uv)' = u'v'.",
            check="Mỗi hạng tử giữ một thừa số chưa đạo hàm.",
            result_latex=sp.latex(derivative),
            kind="transform",
            confidence="symbolic",
        )
    if expression.is_Add:
        after = " + ".join(sp.latex(sp.diff(term, variable)) for term in sp.Add.make_args(expression))
        return AlgebraSolveStep(
            index=index,
            title="Dùng quy tắc tổng",
            explanation="Đạo hàm của tổng bằng tổng các đạo hàm.",
            short_explanation="Tách từng hạng tử để đạo hàm.",
            detail_level="brief",
            method="sum_rule",
            goal="Tách biểu thức thành các hạng tử dễ đạo hàm hơn.",
            why="Quy tắc tổng cho phép xử lý từng hạng tử riêng.",
            rule="(u+v)' = u' + v'",
            operation="Lấy đạo hàm từng hạng tử rồi cộng lại.",
            before_latex=sp.latex(expression),
            after_latex=after,
            check="Cộng các đạo hàm riêng phải ra đạo hàm của tổng.",
            result_latex=sp.latex(derivative),
            kind="transform",
            confidence="symbolic",
        )
    return AlgebraSolveStep(
        index=index,
        title="Dùng bảng đạo hàm cơ bản",
        explanation="Áp dụng trực tiếp công thức đạo hàm cơ bản.",
        short_explanation="Áp dụng công thức đạo hàm cơ bản.",
        detail_level="standard",
        method="basic_derivative_rule",
        goal="Tính đạo hàm của biểu thức.",
        why="Biểu thức khớp với một công thức đạo hàm quen thuộc.",
        rule="Bảng đạo hàm",
        operation="Áp dụng công thức phù hợp rồi rút gọn.",
        before_latex=sp.latex(expression),
        after_latex=sp.latex(sp.diff(expression, variable)),
        check="Có thể kiểm tra lại bằng symbolic diff.",
        result_latex=sp.latex(derivative),
        kind="transform",
        confidence="symbolic",
    )


def _simplify_derivative_step(index: int, expression: sp.Expr, variable: sp.Symbol, derivative: sp.Expr) -> AlgebraSolveStep:
    return AlgebraSolveStep(
        index=index,
        title="Rút gọn kết quả",
        explanation="Rút gọn biểu thức đạo hàm về dạng gọn hơn.",
        short_explanation="Rút gọn đạo hàm.",
        detail_level="standard",
        method="simplify_derivative",
        goal="Viết kết quả cuối cùng rõ ràng.",
        why="Sau khi áp dụng quy tắc đạo hàm, biểu thức có thể còn chưa rút gọn.",
        rule="Rút gọn đại số",
        operation="Thu gọn các tích, tổng và lũy thừa.",
        before_latex=sp.latex(sp.diff(expression, variable)),
        after_latex=sp.latex(derivative),
        pitfall="Không được rút gọn làm thay đổi miền xác định nếu bài yêu cầu xét miền.",
        check="Lấy đạo hàm lại bằng quy tắc hoặc kiểm tra symbolic để đối chiếu.",
        result=sp.sstr(derivative),
        result_latex=sp.latex(derivative),
        kind="solve",
        confidence="verified",
    )


def _higher_order_derivative_steps(expression: sp.Expr, variable: sp.Symbol, derivative: sp.Expr, order: int) -> list[AlgebraSolveStep]:
    steps = [_identify_derivative_step(1, expression, variable)]
    current = expression
    for index in range(1, order + 1):
        next_value = sp.simplify(sp.diff(current, variable))
        steps.append(AlgebraSolveStep(
            index=len(steps) + 1,
            title=f"Tính đạo hàm lần {index}",
            explanation=f"Lấy đạo hàm lần {index} theo {sp.sstr(variable)}.",
            short_explanation=f"Đạo hàm lần {index}.",
            detail_level="standard",
            method="higher_order_derivative",
            goal="Tính đạo hàm cấp cao từng bước.",
            why="Đạo hàm cấp n được tính bằng cách lấy đạo hàm lặp lại n lần.",
            rule="Đạo hàm cấp cao",
            operation="Lấy đạo hàm của kết quả ở bước trước.",
            before_latex=sp.latex(current),
            after_latex=sp.latex(next_value),
            check="Kết quả bước này là đầu vào cho lần đạo hàm tiếp theo.",
            result=sp.sstr(next_value),
            result_latex=sp.latex(next_value),
            kind="solve",
            confidence="symbolic" if index < order else "verified",
        ))
        current = next_value
    return steps


def _direct_substitution(expression: sp.Expr, variable: sp.Symbol, point: sp.Expr) -> tuple[str, str]:
    numerator, denominator = sp.fraction(sp.together(expression))
    try:
        num_value = sp.simplify(numerator.subs(variable, point))
        den_value = sp.simplify(denominator.subs(variable, point))
        if num_value == 0 and den_value == 0:
            return "0/0", r"\frac{0}{0}"
        if denominator != 1 and den_value == 0:
            return f"{sp.sstr(num_value)}/0", rf"\frac{{{sp.latex(num_value)}}}{{0}}"
        direct = sp.simplify(expression.subs(variable, point))
        return sp.sstr(direct), sp.latex(direct)
    except Exception:
        return "không xác định", r"\text{không xác định}"


def _direct_limit_step(index: int, expression: sp.Expr, variable: sp.Symbol, point: sp.Expr, direct: tuple[str, str]) -> AlgebraSolveStep:
    return AlgebraSolveStep(
        index=index,
        title="Thử thay trực tiếp",
        explanation="Thay giá trị tiến tới vào biểu thức để xem có tính được ngay không.",
        short_explanation="Thử thay trực tiếp để nhận dạng dạng giới hạn.",
        detail_level="brief",
        method="direct_substitution_limit",
        goal="Nhận biết giới hạn trực tiếp hay dạng vô định.",
        why="Nếu thay trực tiếp ra giá trị xác định thì đó thường là giới hạn.",
        rule="Thay trực tiếp",
        operation=f"Thay {sp.sstr(variable)} = {sp.sstr(point)} vào biểu thức.",
        before_latex=rf"\lim_{{{sp.latex(variable)}\to {sp.latex(point)}}}{sp.latex(expression)}",
        after_latex=direct[1],
        pitfall="Nếu gặp 0/0 hoặc oo/oo thì chưa được kết luận.",
        check="Kết quả thay trực tiếp phải xác định.",
        result=direct[0],
        result_latex=direct[1],
        kind="transform",
        confidence="symbolic",
    )


def _cancel_limit_step(index: int, expression: sp.Expr, variable: sp.Symbol, point: sp.Expr) -> AlgebraSolveStep | None:
    numerator, denominator = sp.fraction(sp.together(expression))
    try:
        if sp.simplify(numerator.subs(variable, point)) != 0 or sp.simplify(denominator.subs(variable, point)) != 0:
            return None
    except Exception:
        return None
    simplified = sp.cancel(expression)
    if simplified == expression:
        return None
    return AlgebraSolveStep(
        index=index,
        title="Khử dạng vô định 0/0",
        explanation="Biểu thức cho dạng 0/0 nên rút gọn nhân tử chung trước khi lấy giới hạn.",
        short_explanation="Rút gọn nhân tử chung gây 0/0.",
        detail_level="standard",
        method="cancel_common_factor_limit",
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
    )


def _conjugate_limit_step(index: int, expression: sp.Expr, variable: sp.Symbol, point: sp.Expr) -> AlgebraSolveStep | None:
    if not any(isinstance(power, sp.Pow) and power.exp == sp.Rational(1, 2) for power in expression.atoms(sp.Pow)):
        return None
    numerator, denominator = sp.fraction(sp.together(expression))
    conjugate = _conjugate_for(numerator)
    location = "tử"
    if conjugate is None:
        conjugate = _conjugate_for(denominator)
        location = "mẫu"
    if conjugate is None:
        return None
    if location == "tử":
        transformed = sp.cancel(sp.expand(numerator * conjugate) / (denominator * conjugate))
    else:
        transformed = sp.cancel((numerator * conjugate) / sp.expand(denominator * conjugate))
    return AlgebraSolveStep(
        index=index,
        title="Nhân liên hợp",
        explanation=f"Biểu thức có căn ở {location}, nên nhân liên hợp để khử căn gây dạng vô định.",
        short_explanation="Nhân liên hợp để khử căn.",
        detail_level="standard",
        method="conjugate_limit",
        goal="Biến đổi biểu thức chứa căn về dạng dễ rút gọn.",
        why="Liên hợp dùng hằng đẳng thức (a-b)(a+b)=a^2-b^2 để làm mất căn.",
        rule="Nhân liên hợp",
        operation="Nhân cả tử và mẫu với biểu thức liên hợp.",
        before_latex=sp.latex(expression),
        after_latex=sp.latex(transformed),
        pitfall="Phải nhân cả tử và mẫu để không đổi giá trị biểu thức gần điểm xét.",
        check="Biểu thức sau liên hợp phải tương đương biểu thức ban đầu khi mẫu khác 0.",
        result_latex=sp.latex(transformed),
        kind="transform",
        confidence="symbolic",
    )


def _trig_limit_step(index: int, expression: sp.Expr, variable: sp.Symbol, point: sp.Expr) -> AlgebraSolveStep | None:
    if point != 0 or not expression.has(sp.sin, sp.cos, sp.tan):
        return None
    simplified = sp.trigsimp(expression)
    return AlgebraSolveStep(
        index=index,
        title="Dùng giới hạn lượng giác cơ bản",
        explanation="Biểu thức chứa lượng giác gần 0 nên đưa về các giới hạn cơ bản như sin(x)/x.",
        short_explanation="Đưa về giới hạn lượng giác cơ bản.",
        detail_level="standard",
        method="standard_trig_limit",
        goal="Xử lý dạng lượng giác vô định.",
        why="Các giới hạn như sin(u)/u -> 1 là công cụ chuẩn cho giới hạn lượng giác.",
        rule=r"\lim_{u\to0}\frac{\sin u}{u}=1",
        operation="Rút gọn lượng giác và so sánh với giới hạn cơ bản.",
        before_latex=sp.latex(expression),
        after_latex=sp.latex(simplified),
        pitfall="Phải đảm bảo biến phụ u cũng tiến về 0.",
        check="Sau biến đổi, từng nhân tử chuẩn phải có giới hạn xác định.",
        result_latex=sp.latex(simplified),
        kind="transform",
        confidence="symbolic",
    )


def _infinity_limit_step(index: int, expression: sp.Expr, variable: sp.Symbol, point: sp.Expr) -> AlgebraSolveStep | None:
    if point not in {sp.oo, -sp.oo}:
        return None
    numerator, denominator = sp.fraction(sp.together(expression))
    try:
        num_degree = sp.Poly(numerator, variable).degree()
        den_degree = sp.Poly(denominator, variable).degree()
    except sp.PolynomialError:
        return None
    scale = variable ** max(num_degree, den_degree)
    transformed = sp.cancel((numerator / scale) / (denominator / scale))
    return AlgebraSolveStep(
        index=index,
        title="Chia cho lũy thừa bậc cao nhất",
        explanation="Giới hạn tại vô cực của phân thức được xử lý bằng cách chia cho bậc cao nhất.",
        short_explanation="Chia tử và mẫu cho bậc cao nhất.",
        detail_level="standard",
        method="dominant_term_infinity",
        goal="Tìm thành phần chi phối khi biến tiến ra vô cực.",
        why="Các hạng tử bậc thấp mất dần ảnh hưởng khi x tiến tới vô cực.",
        rule="So sánh bậc đa thức",
        operation="Chia cả tử và mẫu cho lũy thừa bậc cao nhất.",
        before_latex=sp.latex(expression),
        after_latex=sp.latex(transformed),
        pitfall="Chọn sai bậc cao nhất sẽ cho kết quả sai.",
        check="Sau khi chia, các hạng chứa 1/x^k tiến về 0.",
        result_latex=sp.latex(transformed),
        kind="transform",
        confidence="symbolic",
    )


def _lhospital_step(index: int, expression: sp.Expr, variable: sp.Symbol, point: sp.Expr) -> AlgebraSolveStep | None:
    numerator, denominator = sp.fraction(sp.together(expression))
    if denominator == 1:
        return None
    try:
        num_limit = sp.limit(numerator, variable, point)
        den_limit = sp.limit(denominator, variable, point)
        if not ((num_limit == 0 and den_limit == 0) or (abs(num_limit) is sp.oo and abs(den_limit) is sp.oo)):
            return None
    except Exception:
        return None
    transformed = sp.diff(numerator, variable) / sp.diff(denominator, variable)
    return AlgebraSolveStep(
        index=index,
        title="Dùng quy tắc L'Hospital",
        explanation="Dạng vô định 0/0 hoặc vô cực/vô cực nên có thể đạo hàm tử và mẫu.",
        short_explanation="Dùng L'Hospital cho dạng vô định.",
        detail_level="detailed",
        method="lhospital",
        goal="Chuyển giới hạn khó thành giới hạn của tỉ số đạo hàm.",
        why="L'Hospital là kỹ thuật nâng cao cho các dạng vô định phù hợp.",
        rule="L'Hospital",
        operation="Lấy đạo hàm tử và đạo hàm mẫu rồi tính giới hạn mới.",
        before_latex=sp.latex(expression),
        after_latex=sp.latex(transformed),
        pitfall="Chỉ dùng khi thỏa điều kiện dạng vô định và các đạo hàm tồn tại gần điểm xét.",
        check="Giới hạn mới phải tồn tại hoặc tiếp tục xử lý được.",
        result_latex=sp.latex(transformed),
        kind="transform",
        confidence="symbolic",
    )


def _identify_integral_step(index: int, expression: sp.Expr, variable: sp.Symbol) -> AlgebraSolveStep:
    return AlgebraSolveStep(
        index=index,
        title="Nhận dạng tích phân",
        explanation="Xác định biểu thức dưới dấu tích phân và biến tích phân.",
        short_explanation="Xác định hàm dưới dấu tích phân.",
        detail_level="brief",
        method="identify_integral",
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
    )


def _basic_integral_step(index: int, expression: sp.Expr, variable: sp.Symbol, antiderivative: sp.Expr) -> AlgebraSolveStep:
    return AlgebraSolveStep(
        index=index,
        title="Tìm nguyên hàm",
        explanation="Tìm một hàm có đạo hàm bằng biểu thức đã cho.",
        short_explanation="Áp dụng bảng nguyên hàm cơ bản.",
        detail_level="standard",
        method="basic_integral",
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
    )


def _u_substitution_integral_step(index: int, expression: sp.Expr, variable: sp.Symbol, antiderivative: sp.Expr) -> AlgebraSolveStep | None:
    for inner in sorted(_candidate_inner_functions(expression, variable), key=lambda item: len(sp.sstr(item)), reverse=True):
        if inner == variable:
            continue
        derivative = sp.diff(inner, variable)
        if derivative == 0:
            continue
        quotient = sp.simplify(expression / derivative)
        u = sp.Symbol("u")
        rewritten = quotient.xreplace({inner: u})
        if not rewritten.has(variable):
            return AlgebraSolveStep(
                index=index,
                title="Đổi biến u",
                explanation="Biểu thức có dạng f'(x)·g(f(x)), nên đặt u=f(x).",
                short_explanation="Đặt u bằng biểu thức bên trong.",
                detail_level="brief",
                method="u_substitution",
                goal="Đưa tích phân về dạng đơn giản theo u.",
                why="Khi thấy đạo hàm của biểu thức bên trong xuất hiện bên ngoài, đổi biến giúp tính nhanh.",
                rule="Đổi biến",
                operation="Đặt u=f(x), du=f'(x)dx.",
                before_latex=rf"\int {sp.latex(expression)}\,d{sp.latex(variable)}",
                after_latex=rf"u={sp.latex(inner)},\quad du={sp.latex(derivative)}\,d{sp.latex(variable)}" + "\n" + sp.latex(antiderivative),
                pitfall="Phải đổi đủ vi phân dx theo du.",
                check="Đạo hàm kết quả phải ra lại integrand ban đầu.",
                result=sp.sstr(antiderivative),
                result_latex=sp.latex(antiderivative),
                kind="solve",
                confidence="symbolic",
            )
    return None


def _integration_by_parts_step(index: int, expression: sp.Expr, variable: sp.Symbol, antiderivative: sp.Expr) -> AlgebraSolveStep | None:
    if not expression.is_Mul:
        return None
    factors = sp.Mul.make_args(expression)
    has_poly = any(_is_polynomial_factor(factor, variable) for factor in factors)
    has_exp_log_trig = any(factor.has(sp.exp, sp.log, sp.sin, sp.cos) for factor in factors)
    if not has_poly or not has_exp_log_trig:
        return None
    return AlgebraSolveStep(
        index=index,
        title="Tích phân từng phần",
        explanation="Tích phân là tích của đa thức với hàm mũ/log/lượng giác nên dùng từng phần.",
        short_explanation="Dùng công thức từng phần.",
        detail_level="standard",
        method="integration_by_parts",
        goal="Giảm tích phân của tích hai hàm.",
        why="Chọn u là phần đa thức thường làm đạo hàm đơn giản dần.",
        rule=r"\int u\,dv=uv-\int v\,du",
        operation="Chọn u và dv, tính du và v rồi áp dụng công thức.",
        before_latex=rf"\int {sp.latex(expression)}\,d{sp.latex(variable)}",
        after_latex=sp.latex(antiderivative),
        pitfall="Chọn u không phù hợp có thể làm tích phân phức tạp hơn.",
        check="Đạo hàm kết quả phải ra lại biểu thức ban đầu.",
        result=sp.sstr(antiderivative),
        result_latex=sp.latex(antiderivative),
        kind="solve",
        confidence="symbolic",
    )


def _partial_fraction_integral_step(index: int, expression: sp.Expr, variable: sp.Symbol, antiderivative: sp.Expr) -> AlgebraSolveStep | None:
    numerator, denominator = sp.fraction(sp.together(expression))
    if denominator == 1 or not denominator.has(variable):
        return None
    apart = sp.apart(expression, variable)
    if sp.simplify(apart - expression) != 0 or apart == expression:
        return None
    return AlgebraSolveStep(
        index=index,
        title="Phân tích phân thức",
        explanation="Phân thức hữu tỉ được tách thành các phân thức đơn giản trước khi lấy tích phân.",
        short_explanation="Tách phân thức thành các phần đơn giản.",
        detail_level="standard",
        method="partial_fractions",
        goal="Đưa tích phân phân thức về tổng các tích phân cơ bản.",
        why="Mỗi phân thức đơn giản thường cho log hoặc lũy thừa quen thuộc.",
        rule="Partial fractions",
        operation="Dùng phân tích phân thức rồi tích phân từng hạng.",
        before_latex=rf"\int {sp.latex(expression)}\,d{sp.latex(variable)}",
        after_latex=sp.latex(apart) + "\n" + sp.latex(antiderivative),
        pitfall="Phải phân tích đúng mẫu số trước khi tách.",
        check="Cộng các phân thức sau tách phải ra phân thức ban đầu.",
        result=sp.sstr(antiderivative),
        result_latex=sp.latex(antiderivative),
        kind="solve",
        confidence="symbolic",
    )


def _trig_identity_integral_step(index: int, expression: sp.Expr, variable: sp.Symbol, antiderivative: sp.Expr) -> AlgebraSolveStep | None:
    expanded = sp.expand_trig(expression)
    rewritten = None
    if expression == sp.sin(variable) ** 2:
        rewritten = (1 - sp.cos(2 * variable)) / 2
    elif expression == sp.cos(variable) ** 2:
        rewritten = (1 + sp.cos(2 * variable)) / 2
    elif expanded != expression and expression.has(sp.sin, sp.cos, sp.tan):
        rewritten = expanded
    if rewritten is None:
        return None
    return AlgebraSolveStep(
        index=index,
        title="Dùng đồng nhất thức lượng giác",
        explanation="Biến đổi biểu thức lượng giác về dạng dễ lấy nguyên hàm.",
        short_explanation="Dùng công thức lượng giác để hạ bậc/rút gọn.",
        detail_level="standard",
        method="trig_identity_integral",
        goal="Đưa tích phân lượng giác về bảng nguyên hàm cơ bản.",
        why="Các lũy thừa lượng giác thường cần hạ bậc trước khi tích phân.",
        rule="Công thức hạ bậc",
        operation="Thay biểu thức bằng đồng nhất thức tương đương rồi lấy tích phân.",
        before_latex=rf"\int {sp.latex(expression)}\,d{sp.latex(variable)}",
        after_latex=rf"\int {sp.latex(rewritten)}\,d{sp.latex(variable)}" + "\n" + sp.latex(antiderivative),
        pitfall="Không được quên hệ số 1/2 trong công thức hạ bậc.",
        check="Đạo hàm nguyên hàm phải ra lại biểu thức ban đầu.",
        result=sp.sstr(antiderivative),
        result_latex=sp.latex(antiderivative),
        kind="solve",
        confidence="symbolic",
    )


def _definite_integral_step(index: int, variable: sp.Symbol, antiderivative: sp.Expr, result: sp.Expr, lower: sp.Expr, upper: sp.Expr) -> AlgebraSolveStep:
    return AlgebraSolveStep(
        index=index,
        title="Thay cận tích phân",
        explanation="Dùng công thức Newton-Leibniz cho tích phân xác định.",
        short_explanation="Tính F(b)-F(a).",
        detail_level="standard",
        method="newton_leibniz",
        goal="Tính giá trị số của tích phân xác định.",
        why="Giá trị tích phân từ a đến b bằng F(b) - F(a).",
        rule="Newton-Leibniz",
        operation="Lấy nguyên hàm tại cận trên trừ nguyên hàm tại cận dưới.",
        before_latex=rf"\left[{sp.latex(antiderivative)}\right]_{{{sp.latex(lower)}}}^{{{sp.latex(upper)}}}",
        after_latex=rf"{sp.latex(antiderivative.subs(variable, upper))}-{sp.latex(antiderivative.subs(variable, lower))}={sp.latex(result)}",
        pitfall="Không đổi thứ tự cận trên và cận dưới.",
        check="Nếu đổi cận, kết quả phải đổi dấu.",
        result=sp.sstr(result),
        result_latex=sp.latex(result),
        kind="solve",
        confidence="verified",
    )


def _is_chain_expression(expression: sp.Expr, variable: sp.Symbol) -> bool:
    if expression.func in {sp.sin, sp.cos, sp.tan, sp.log, sp.exp} and expression.args and expression.args[0].has(variable) and expression.args[0] != variable:
        return True
    return isinstance(expression, sp.Pow) and expression.base.has(variable) and not expression.exp.has(variable)


def _conjugate_for(expression: sp.Expr) -> sp.Expr | None:
    if not expression.is_Add or len(expression.args) != 2:
        return None
    a, b = expression.args
    if not (a.has(sp.sqrt) or b.has(sp.sqrt) or any(isinstance(power, sp.Pow) and power.exp == sp.Rational(1, 2) for power in expression.atoms(sp.Pow))):
        return None
    return a - b


def _candidate_inner_functions(expression: sp.Expr, variable: sp.Symbol) -> set[sp.Expr]:
    candidates: set[sp.Expr] = set()
    for func in (sp.sin, sp.cos, sp.exp, sp.log):
        for item in expression.atoms(func):
            if item.args and item.args[0].has(variable):
                candidates.add(item.args[0])
    for power in expression.atoms(sp.Pow):
        if power.base.has(variable) and not power.exp.has(variable):
            candidates.add(power.base)
    return candidates


def _is_polynomial_factor(expression: sp.Expr, variable: sp.Symbol) -> bool:
    try:
        poly = sp.Poly(expression, variable)
    except sp.PolynomialError:
        return False
    return poly.degree() >= 1
