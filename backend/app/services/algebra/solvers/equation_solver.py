from __future__ import annotations

from dataclasses import dataclass

import sympy as sp

from app.schemas.algebra import AlgebraSolutionSet, AlgebraSolutionValue, AlgebraSolveResponse, AlgebraSolveStep, AlgebraVerificationReport
from app.services.algebra.domain import domain_assumptions_from_expression
from app.services.algebra.formatting import format_solution_set, solution_values
from app.services.algebra.parser import ParsedAlgebraProblem
from app.services.algebra.steps import conclusion_step, domain_step, method_step
from app.services.algebra.transformations import detect_primary_technique, rational_parts
from app.services.algebra.verifier import verify_finite_solutions, verify_solution_set


def solve_equation(problem: ParsedAlgebraProblem) -> AlgebraSolveResponse:
    if problem.relation is None or not isinstance(problem.relation, sp.Equality):
        return _unsupported(problem, "Đầu vào không phải phương trình.")
    variable = problem.variable
    raw_expression = problem.relation.lhs - problem.relation.rhs
    expression = sp.simplify(raw_expression)
    solve_expression = _equation_expression_after_safe_transform(raw_expression, variable)
    assumptions = domain_assumptions_from_expression(raw_expression, variable)
    
    milestones: list[str] = []
    if problem.relation is not None:
        milestones.append(f"Phương trình gốc: {sp.latex(problem.relation)}")
    
    try:
        factored_expr = sp.factor(expression)
        if factored_expr != expression and not isinstance(factored_expr, sp.Add):
            milestones.append(f"Dạng phân tích nhân tử: {sp.latex(sp.Eq(factored_expr, 0, evaluate=False))}")
    except Exception:
        pass
        
    steps: list[AlgebraSolveStep] = []
    if assumptions and _should_add_initial_domain_step(raw_expression, variable):
        steps.append(domain_step(len(steps) + 1, assumptions))
    steps.append(method_step(len(steps) + 1, detect_primary_technique("equation", raw_expression, variable)))
    try:
        solution_set = sp.solveset(raw_expression, variable, domain=problem.sympy_domain)
        if problem.solve_interval is not None:
            solution_set = solution_set.intersect(problem.solve_interval)
    except Exception as exc:
        return _unsupported(problem, f"SymPy chưa giải được phương trình này: {exc}")
    values = solution_values(solution_set)
    interval_note = (
        f"Nghiệm đã được lọc theo khoảng người dùng chọn: {sp.latex(problem.solve_interval)}."
        if problem.solve_interval is not None
        else None
    )
    
    if values is not None and len(values) > 0:
        roots_latex = ", ".join(sp.latex(sp.Eq(variable, val, evaluate=False)) for val in values)
        milestones.append(f"Tập nghiệm: {roots_latex}")
        
    steps.extend(_technique_steps(problem, raw_expression, variable, len(steps) + 1))
    detailed_steps = (
        _absolute_value_steps(problem, raw_expression, variable, values, start_index=len(steps) + 1)
        or _radical_equation_steps(problem, expression, variable, values, start_index=len(steps) + 1)
        or _biquadratic_steps(solve_expression, variable, start_index=len(steps) + 1)
        or _rational_root_division_steps(solve_expression, variable, start_index=len(steps) + 1)
        or _factor_steps(solve_expression, variable, start_index=len(steps) + 1)
        or _quadratic_steps(solve_expression, variable, start_index=len(steps) + 1)
        or _depressed_cubic_steps(solve_expression, variable, start_index=len(steps) + 1)
        or _generic_radical_steps(problem, expression, variable, len(steps) + 1)
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
    answer, answer_latex = _display_answer(solve_expression, variable, solution_set, values)
    solution = AlgebraSolutionSet(
        kind="empty" if solution_set is sp.EmptySet else "finite" if values is not None else "set",
        text=answer,
        latex=sp.latex(solution_set),
        values=[AlgebraSolutionValue(text=sp.sstr(value), latex=sp.latex(value), approximate=str(sp.N(value, 8))) for value in values or []],
    )
    verification = verify_finite_solutions(problem, values) if values is not None else verify_solution_set(problem, solution_set)
    status = "solved" if verification.status in {"verified", "partially_verified"} else "error"
    if values is not None and _needs_filter_step(raw_expression, variable) and not _has_candidate_filter_step(steps):
        steps.append(_filter_candidates_step(len(steps) + 1, problem, values))
    steps.append(_verification_step(len(steps) + 1, verification, values, solution_set, problem, raw_expression))
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
        milestones=milestones,
        verification=verification,
        assumptions=assumptions,
        warnings=[
            *([] if values is not None else ["Tập nghiệm symbolic không hữu hạn nên chỉ kiểm chứng ở mức biểu diễn tập nghiệm."]),
            *([interval_note] if interval_note else []),
        ],
        errors=[] if status == "solved" else ["Kiểm chứng nghiệm thất bại."],
    )


def _unsupported(problem: ParsedAlgebraProblem, message: str) -> AlgebraSolveResponse:
    return AlgebraSolveResponse(input=problem.raw_input, normalized_input=problem.normalized_input, topic="equation", problem_type="solve_equation", status="unsupported", answer=message, errors=[message])


def _should_add_initial_domain_step(expression: sp.Expr, variable: sp.Symbol) -> bool:
    denominator = sp.denom(sp.together(expression))
    if denominator != 1 and denominator.has(variable):
        return True
    return any(log_expr.args[0].has(variable) for log_expr in expression.atoms(sp.log))


def _equation_expression_after_safe_transform(raw_expression: sp.Expr, variable: sp.Symbol) -> sp.Expr:
    rational_expression = sp.together(raw_expression)
    numerator, denominator = sp.fraction(rational_expression)
    if denominator != 1 and denominator.has(variable):
        return sp.factor(numerator)
    return sp.simplify(raw_expression)


def _technique_steps(problem: ParsedAlgebraProblem, expression: sp.Expr, variable: sp.Symbol, start_index: int) -> list[AlgebraSolveStep]:
    steps: list[AlgebraSolveStep] = []
    rational_step = _rational_clear_denominator_step(problem, expression, variable, start_index)
    if rational_step:
        steps.append(rational_step)
    return steps


def _absolute_value_steps(
    problem: ParsedAlgebraProblem,
    expression: sp.Expr,
    variable: sp.Symbol,
    final_values: list[sp.Expr] | None,
    start_index: int,
) -> list[AlgebraSolveStep]:
    """Pedagogical case-split notes for Abs equations (solve still uses solveset)."""
    abs_atoms = [atom for atom in expression.atoms(sp.Abs) if atom.args and atom.args[0].has(variable)]
    if not abs_atoms or len(abs_atoms) > 2:
        return []
    notes: list[str] = []
    for atom in abs_atoms:
        g = atom.args[0]
        notes.append(
            rf"{sp.latex(atom)}:\ g={sp.latex(g)}\ge 0 \Rightarrow {sp.latex(atom)}={sp.latex(g)};\ "
            rf"g<0 \Rightarrow {sp.latex(atom)}={sp.latex(-g)}"
        )
    result_latex = (
        ", ".join(sp.latex(sp.Eq(variable, val, evaluate=False)) for val in final_values)
        if final_values
        else None
    )
    return [
        AlgebraSolveStep(
            index=start_index,
            title="Xét dấu trị tuyệt đối",
            explanation=(
                "Phương trình có trị tuyệt đối; chia miền theo zero của biểu thức trong |·| "
                "rồi ghép nghiệm. " + " ".join(notes)
            ),
            short_explanation="Case-split theo định nghĩa |g|.",
            method="abs_case_split",
            goal="Chia miền g≥0 và g<0 cho từng Abs.",
            why="|g|=g khi g≥0 và |g|=−g khi g<0.",
            rule="Định nghĩa trị tuyệt đối",
            operation="Viết hai trường hợp theo dấu của biểu thức trong Abs.",
            before_latex=sp.latex(problem.relation) if problem.relation is not None else sp.latex(expression),
            after_latex="; ".join(notes),
            pitfall="Phải kiểm tra nghiệm thuộc đúng miền đã giả sử.",
            check="Thay nghiệm vào phương trình gốc (có Abs).",
            expression=sp.sstr(expression),
            expression_latex=sp.latex(expression),
            kind="transform",
            confidence="symbolic",
        ),
        AlgebraSolveStep(
            index=start_index + 1,
            title="Giải và ghép nghiệm",
            explanation="Dùng solveset trên R; các nghiệm ứng viên được kiểm chứng bằng thay vào đề gốc.",
            method="abs_solveset",
            goal="Tìm nghiệm thỏa phương trình Abs.",
            why="SymPy solveset xử lý Abs trên miền thực; bước trên giải thích case-split sư phạm.",
            rule="solveset + verify",
            operation="Giải symbolic rồi lọc bằng substitution.",
            result="; ".join(sp.sstr(v) for v in (final_values or [])),
            result_latex=result_latex,
            kind="solve",
            confidence="symbolic",
        ),
    ]


def _has_candidate_filter_step(steps: list[AlgebraSolveStep]) -> bool:
    return any(step.title == "Lọc nghiệm ngoại lai" for step in steps)


def _rational_clear_denominator_step(problem: ParsedAlgebraProblem, expression: sp.Expr, variable: sp.Symbol, index: int) -> AlgebraSolveStep | None:
    parts = rational_parts(expression, variable)
    if parts is None:
        return None
    numerator, denominator = parts
    rational_expression = sp.together(expression)
    return AlgebraSolveStep(
        index=index,
        title="Quy đồng và khử mẫu",
        explanation="Vì phương trình có phân thức, trước hết cần ghi điều kiện mẫu khác 0 rồi đưa về phương trình tử số bằng 0.",
        short_explanation="Giữ điều kiện mẫu khác 0, rồi giải tử số bằng 0.",
        detail_level="standard",
        method="clear_denominator",
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


def _generic_radical_steps(problem: ParsedAlgebraProblem, expression: sp.Expr, variable: sp.Symbol, start_index: int) -> list[AlgebraSolveStep]:
    step = _radical_method_step(problem, expression, variable, start_index)
    return [step] if step else []


@dataclass(frozen=True)
class RadicalIsolation:
    radical: sp.Pow
    coefficient: sp.Expr
    base: sp.Expr
    rhs: sp.Expr
    squared_expression: sp.Expr


def _radical_equation_steps(problem: ParsedAlgebraProblem, expression: sp.Expr, variable: sp.Symbol, final_values: list[sp.Expr] | None, start_index: int) -> list[AlgebraSolveStep]:
    if not _has_even_root(expression, variable):
        return []
    radical_count = len(_radical_powers(expression, variable))
    if radical_count == 1:
        return _single_radical_equation_steps(problem, expression, variable, final_values, start_index)
    if radical_count == 2:
        return _double_radical_equation_steps(problem, expression, variable, final_values, start_index)
    return []


def _single_radical_equation_steps(problem: ParsedAlgebraProblem, expression: sp.Expr, variable: sp.Symbol, final_values: list[sp.Expr] | None, start_index: int) -> list[AlgebraSolveStep]:
    isolation = _isolate_single_radical(expression, variable)
    if isolation is None:
        return []
    return _radical_solution_steps(problem, expression, variable, final_values, isolation, start_index, include_domain=True)


def _double_radical_equation_steps(problem: ParsedAlgebraProblem, expression: sp.Expr, variable: sp.Symbol, final_values: list[sp.Expr] | None, start_index: int) -> list[AlgebraSolveStep]:
    first_isolation = _isolate_one_radical_term(expression, variable, allow_radical_rhs=True)
    if first_isolation is None:
        return []
    second_isolation = _isolate_single_radical(first_isolation.squared_expression, variable)
    if second_isolation is None:
        return []
    second_squared = sp.expand(second_isolation.squared_expression)
    if _has_even_root(second_squared, variable):
        return []
    candidate_values = _finite_real_values(second_squared, variable)
    if candidate_values is None:
        return []

    steps = [_radical_domain_step(problem, expression, variable, start_index)]
    steps.append(AlgebraSolveStep(
        index=start_index + 1,
        title="Cô lập căn thứ nhất",
        explanation="Chuyển một căn sang một vế để khi bình phương chỉ còn một căn ở phương trình mới.",
        goal="Giảm số căn xuất hiện trong phương trình.",
        why="Muốn bình phương hiệu quả, một vế nên chỉ có một căn.",
        rule="Cô lập căn",
        operation="Giữ một căn ở vế trái, chuyển các hạng tử còn lại sang vế phải.",
        before_latex=sp.latex(sp.Eq(expression, 0, evaluate=False)),
        after_latex=sp.latex(sp.Eq(first_isolation.radical, first_isolation.rhs, evaluate=False)),
        pitfall="Bình phương khi chưa cô lập căn thường làm biểu thức phức tạp hơn.",
        check="Hai vế sau khi chuyển vế phải vẫn tương đương với phương trình trước đó.",
        expression=sp.sstr(expression),
        expression_latex=sp.latex(sp.Eq(expression, 0, evaluate=False)),
        result=sp.sstr(first_isolation.rhs),
        result_latex=sp.latex(sp.Eq(first_isolation.radical, first_isolation.rhs, evaluate=False)),
        kind="transform",
        confidence="symbolic",
    ))
    steps.append(AlgebraSolveStep(
        index=start_index + 2,
        title="Bình phương lần một",
        explanation="Bình phương hai vế để khử căn đã cô lập; phương trình mới còn một căn nên cần xử lý tiếp.",
        goal="Khử bớt một căn khỏi phương trình.",
        why="Nếu hai vế không âm và bằng nhau thì bình phương hai vế vẫn giữ được nghiệm, nhưng có thể sinh nghiệm ngoại lai.",
        rule="Bình phương hai vế",
        operation="Bình phương hai vế của phương trình vừa cô lập.",
        before_latex=sp.latex(sp.Eq(first_isolation.radical, first_isolation.rhs, evaluate=False)),
        after_latex=sp.latex(sp.Eq(first_isolation.squared_expression, 0, evaluate=False)),
        pitfall="Sau khi bình phương lần một vẫn chưa được kết luận nghiệm.",
        check="Phương trình sau bình phương phải còn ít căn hơn phương trình ban đầu.",
        expression=sp.sstr(first_isolation.squared_expression),
        expression_latex=sp.latex(sp.Eq(first_isolation.squared_expression, 0, evaluate=False)),
        result_latex=sp.latex(sp.Eq(first_isolation.squared_expression, 0, evaluate=False)),
        kind="transform",
        confidence="symbolic",
    ))
    steps.append(AlgebraSolveStep(
        index=start_index + 3,
        title="Cô lập căn còn lại",
        explanation="Phương trình sau lần bình phương thứ nhất vẫn còn căn, nên tiếp tục cô lập căn đó.",
        goal="Chuẩn bị khử căn còn lại.",
        why="Cô lập căn giúp lần bình phương tiếp theo đưa phương trình về dạng không còn căn.",
        rule="Cô lập căn",
        operation="Chuyển các hạng tử không chứa căn sang vế còn lại.",
        before_latex=sp.latex(sp.Eq(first_isolation.squared_expression, 0, evaluate=False)),
        after_latex=sp.latex(sp.Eq(second_isolation.radical, second_isolation.rhs, evaluate=False)),
        pitfall="Cần giữ đúng dấu khi chuyển vế, nhất là khi căn có hệ số âm.",
        check="Thay biểu thức vừa cô lập vào phương trình trước phải đúng.",
        expression=sp.sstr(first_isolation.squared_expression),
        expression_latex=sp.latex(sp.Eq(first_isolation.squared_expression, 0, evaluate=False)),
        result=sp.sstr(second_isolation.rhs),
        result_latex=sp.latex(sp.Eq(second_isolation.radical, second_isolation.rhs, evaluate=False)),
        kind="transform",
        confidence="symbolic",
    ))
    steps.append(_square_radical_step(second_isolation, second_squared, start_index + 4, title="Bình phương lần hai"))
    steps.extend(_candidate_equation_steps(second_squared, variable, start_index + len(steps)))
    steps.append(_radical_candidate_filter_step(start_index + len(steps), problem, candidate_values, final_values or []))
    return _reindex_steps(steps, start_index)


def _radical_solution_steps(
    problem: ParsedAlgebraProblem,
    original_expression: sp.Expr,
    variable: sp.Symbol,
    final_values: list[sp.Expr] | None,
    isolation: RadicalIsolation,
    start_index: int,
    include_domain: bool,
) -> list[AlgebraSolveStep]:
    squared_expression = sp.expand(isolation.squared_expression)
    if _has_even_root(squared_expression, variable):
        return []
    candidate_values = _finite_real_values(squared_expression, variable)
    if candidate_values is None:
        return []

    steps: list[AlgebraSolveStep] = []
    if include_domain:
        steps.append(_radical_domain_step(problem, original_expression, variable, start_index))
    steps.append(AlgebraSolveStep(
        index=start_index + len(steps),
        title="Cô lập căn",
        explanation="Đưa căn thức về một vế, các hạng tử còn lại sang vế kia.",
        goal="Chuẩn bị bình phương hai vế để khử căn.",
        why="Bình phương trực tiếp khi căn chưa được cô lập dễ tạo phương trình khó hơn và dễ sai dấu.",
        rule="Cô lập căn thức",
        operation="Chuyển vế để được một căn bằng một biểu thức không chứa căn.",
        before_latex=sp.latex(sp.Eq(original_expression, 0, evaluate=False)),
        after_latex=sp.latex(sp.Eq(isolation.radical, isolation.rhs, evaluate=False)),
        pitfall="Vế phải sau khi cô lập cũng phải không âm nếu muốn hai vế thật sự bằng nhau.",
        check="Thay đổi chỉ là chuyển vế và chia hệ số, chưa làm mất hay thêm nghiệm.",
        expression=sp.sstr(original_expression),
        expression_latex=sp.latex(sp.Eq(original_expression, 0, evaluate=False)),
        result=sp.sstr(isolation.rhs),
        result_latex=sp.latex(sp.Eq(isolation.radical, isolation.rhs, evaluate=False)),
        kind="transform",
        confidence="symbolic",
    ))
    steps.append(_square_radical_step(isolation, squared_expression, start_index + len(steps), title="Bình phương hai vế"))
    steps.extend(_candidate_equation_steps(squared_expression, variable, start_index + len(steps)))
    steps.append(_radical_candidate_filter_step(start_index + len(steps), problem, candidate_values, final_values or []))
    return _reindex_steps(steps, start_index)


def _radical_domain_step(problem: ParsedAlgebraProblem, expression: sp.Expr, variable: sp.Symbol, index: int) -> AlgebraSolveStep:
    conditions = _radical_condition_lines(expression, variable)
    return AlgebraSolveStep(
        index=index,
        title="Điều kiện căn thức",
        explanation="Trước khi bình phương, ghi điều kiện để các biểu thức trong căn bậc hai không âm.",
        goal="Xác định miền giá trị có thể nhận của biến.",
        why="Căn bậc hai trong tập số thực chỉ xác định khi biểu thức dưới căn không âm.",
        rule="Điều kiện xác định của căn bậc hai",
        operation="Cho từng biểu thức dưới căn lớn hơn hoặc bằng 0.",
        before_latex=sp.latex(problem.relation) if problem.relation is not None else sp.latex(sp.Eq(expression, 0, evaluate=False)),
        after_latex="\n".join(conditions) if conditions else r"\text{Không có điều kiện căn theo biến}",
        pitfall="Không được bỏ qua điều kiện này vì nghiệm sau bình phương có thể không hợp lệ.",
        check="Mỗi nghiệm cuối cùng phải thỏa tất cả điều kiện dưới căn.",
        expression=sp.sstr(expression),
        expression_latex=sp.latex(sp.Eq(expression, 0, evaluate=False)),
        result_latex="\n".join(conditions) if conditions else None,
        kind="domain",
        confidence="symbolic",
    )


def _square_radical_step(isolation: RadicalIsolation, squared_expression: sp.Expr, index: int, title: str) -> AlgebraSolveStep:
    return AlgebraSolveStep(
        index=index,
        title=title,
        explanation="Bình phương hai vế để loại căn thức đã cô lập.",
        goal="Đưa phương trình về dạng không còn căn ở bước đang xét.",
        why="Vì hai vế bằng nhau, ta xét bình phương hai vế; bước này có thể sinh nghiệm ngoại lai nên phải thử lại.",
        rule="Bình phương hai vế",
        operation="Lấy bình phương vế trái và vế phải rồi rút gọn.",
        before_latex=sp.latex(sp.Eq(isolation.radical, isolation.rhs, evaluate=False)),
        after_latex=sp.latex(sp.Eq(squared_expression, 0, evaluate=False)),
        pitfall="Bình phương không phải phép tương đương hai chiều nếu không kiểm tra điều kiện dấu.",
        check="Nghiệm tìm được từ phương trình sau bình phương chỉ là nghiệm ứng viên.",
        expression=sp.sstr(squared_expression),
        expression_latex=sp.latex(sp.Eq(squared_expression, 0, evaluate=False)),
        result=sp.sstr(squared_expression),
        result_latex=sp.latex(sp.Eq(squared_expression, 0, evaluate=False)),
        kind="transform",
        confidence="symbolic",
    )


def _candidate_equation_steps(expression: sp.Expr, variable: sp.Symbol, start_index: int) -> list[AlgebraSolveStep]:
    steps = (
        _biquadratic_steps(expression, variable, start_index)
        or _rational_root_division_steps(expression, variable, start_index)
        or _factor_steps(expression, variable, start_index)
        or _quadratic_steps(expression, variable, start_index)
    )
    if steps:
        return steps
    solution_values_for_expression = _finite_real_values(expression, variable) or []
    candidates_latex = _or_join([rf"{sp.latex(variable)}={sp.latex(value)}" for value in solution_values_for_expression]) if solution_values_for_expression else r"\varnothing"
    return [AlgebraSolveStep(
        index=start_index,
        title="Giải phương trình sau bình phương",
        explanation="Giải phương trình không còn căn để lấy nghiệm ứng viên.",
        goal="Tìm các giá trị có thể là nghiệm của phương trình gốc.",
        why="Sau bình phương, nghiệm thu được cần được kiểm tra lại với phương trình ban đầu.",
        rule="Giải phương trình ứng viên",
        operation="Giải phương trình sau khi khử căn.",
        before_latex=sp.latex(sp.Eq(expression, 0, evaluate=False)),
        after_latex=candidates_latex,
        pitfall="Không kết luận ngay ở bước này vì có thể có nghiệm ngoại lai.",
        check="Mỗi nghiệm ứng viên phải được thay lại vào phương trình gốc.",
        expression=sp.sstr(expression),
        expression_latex=sp.latex(sp.Eq(expression, 0, evaluate=False)),
        result="; ".join(sp.sstr(value) for value in solution_values_for_expression),
        result_latex=r"\left\{" + ", ".join(sp.latex(value) for value in solution_values_for_expression) + r"\right\}",
        kind="solve",
        confidence="symbolic",
    )]


def _radical_candidate_filter_step(index: int, problem: ParsedAlgebraProblem, candidates: list[sp.Expr], valid_values: list[sp.Expr]) -> AlgebraSolveStep:
    candidate_lines: list[str] = []
    for candidate in candidates:
        is_valid = any(sp.simplify(candidate - value) == 0 for value in valid_values)
        marker = r"\text{giữ}" if is_valid else r"\text{loại}"
        candidate_lines.append(rf"{sp.latex(problem.variable)}={sp.latex(candidate)}:\quad {marker}")
    if not candidate_lines:
        candidate_lines.append(r"\text{Không có nghiệm ứng viên}")
    result_latex = r"S=\left\{" + ", ".join(sp.latex(value) for value in valid_values) + r"\right\}" if valid_values else r"S=\varnothing"
    return AlgebraSolveStep(
        index=index,
        title="Lọc nghiệm ngoại lai",
        explanation="Thay từng nghiệm ứng viên vào phương trình gốc và điều kiện căn thức.",
        goal="Giữ lại đúng nghiệm của phương trình ban đầu.",
        why="Bình phương hai vế có thể tạo nghiệm làm phương trình sau bình phương đúng nhưng phương trình gốc sai.",
        rule="Thử lại nghiệm sau bình phương",
        operation="Thay từng nghiệm ứng viên vào phương trình ban đầu.",
        before_latex=sp.latex(problem.relation) if problem.relation is not None else None,
        after_latex="\n".join(candidate_lines + [result_latex]),
        pitfall="Không được lấy toàn bộ nghiệm của phương trình sau bình phương làm đáp án.",
        check="Nghiệm giữ lại phải thỏa điều kiện căn và làm phương trình gốc đúng.",
        result="; ".join(sp.sstr(value) for value in valid_values) if valid_values else "Không còn nghiệm hợp lệ",
        result_latex=result_latex,
        kind="verify",
        confidence="verified",
    )


def _isolate_single_radical(expression: sp.Expr, variable: sp.Symbol) -> RadicalIsolation | None:
    radical_terms = _radical_terms(expression, variable)
    if len(radical_terms) != 1:
        return None
    return _isolate_one_radical_term(expression, variable, allow_radical_rhs=False)


def _isolate_one_radical_term(expression: sp.Expr, variable: sp.Symbol, allow_radical_rhs: bool) -> RadicalIsolation | None:
    radical_terms = _radical_terms(expression, variable)
    if not radical_terms:
        return None
    term, radical = radical_terms[0]
    coefficient = sp.simplify(term / radical)
    if coefficient.has(variable) or coefficient == 0:
        return None
    rest = sp.simplify(expression - term)
    rhs = sp.simplify(-rest / coefficient)
    if not allow_radical_rhs and _has_even_root(rhs, variable):
        return None
    squared_expression = sp.expand(radical.base - rhs**2)
    return RadicalIsolation(radical=radical, coefficient=coefficient, base=radical.base, rhs=rhs, squared_expression=squared_expression)


def _radical_terms(expression: sp.Expr, variable: sp.Symbol) -> list[tuple[sp.Expr, sp.Pow]]:
    terms: list[tuple[sp.Expr, sp.Pow]] = []
    for term in sp.Add.make_args(expression):
        radicals = [radical for radical in _radical_powers(term, variable) if radical.has(variable)]
        if len(radicals) != 1:
            continue
        terms.append((term, radicals[0]))
    return terms


def _radical_powers(expression: sp.Expr, variable: sp.Symbol) -> list[sp.Pow]:
    radicals = [
        power
        for power in expression.atoms(sp.Pow)
        if power.base.has(variable) and power.exp == sp.Rational(1, 2)
    ]
    return sorted(radicals, key=sp.default_sort_key)


def _radical_condition_lines(expression: sp.Expr, variable: sp.Symbol) -> list[str]:
    return [sp.latex(sp.Ge(radical.base, 0, evaluate=False)) for radical in _radical_powers(expression, variable)]


def _finite_real_values(expression: sp.Expr, variable: sp.Symbol) -> list[sp.Expr] | None:
    try:
        solution_set = sp.solveset(expression, variable, domain=sp.S.Reals)
    except Exception:
        return None
    values = solution_values(solution_set)
    if values is None:
        return None
    return sorted(values, key=sp.default_sort_key)


def _reindex_steps(steps: list[AlgebraSolveStep], start_index: int) -> list[AlgebraSolveStep]:
    reindexed: list[AlgebraSolveStep] = []
    for offset, step in enumerate(steps):
        reindexed.append(step.model_copy(update={"index": start_index + offset}))
    return reindexed


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


def _verification_step(index: int, verification: AlgebraVerificationReport, values: list[sp.Expr] | None, solution_set: sp.Set, problem: ParsedAlgebraProblem, expression: sp.Expr) -> AlgebraSolveStep:
    if values is None:
        result_latex = sp.latex(solution_set)
        result = sp.sstr(solution_set)
        explanation = "Tập nghiệm ở dạng biểu thức tập, nên kiểm tra bằng điều kiện mô tả tập nghiệm."
        short_explanation = "Đối chiếu tập nghiệm symbolic với đề gốc."
        operation = "Đối chiếu tập nghiệm với phương trình ban đầu."
        check = "Đọc cảnh báo nếu tập nghiệm không hữu hạn hoặc chưa thể thay từng nghiệm cụ thể."
    else:
        result_latex = _substitution_check_latex(problem, expression, values)
        result = "; ".join(sp.sstr(value) for value in values) if values else "Không có nghiệm hữu hạn"
        check_summary = _verification_check_summary(verification)
        explanation = check_summary or "Thay lại từng nghiệm vào phương trình ban đầu để chắc chắn không có nghiệm ngoại lai."
        short_explanation = "Kiểm tra điều kiện xác định và thay nghiệm vào phương trình gốc."
        operation = "Thay nghiệm vào phương trình gốc."
        check = "Mỗi nghiệm phải làm hai vế bằng nhau và thỏa điều kiện xác định."
    confidence = "verified" if verification.status == "verified" else "symbolic" if verification.status == "partially_verified" else "unverified"
    return AlgebraSolveStep(
        index=index,
        title="Thử lại nghiệm",
        explanation=explanation,
        short_explanation=short_explanation,
        detail_level="standard",
        method="substitution_check",
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


def _verification_check_summary(verification: AlgebraVerificationReport) -> str:
    useful = [
        check.detail
        for check in verification.checks
        if check.name in {"domain_constraints_valid", "candidate_substitution"}
    ]
    return " ".join(useful[:6])


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
    if (
        values is not None
        and _polynomial_degree(expression, variable) is not None
        and (_polynomial_degree(expression, variable) or 0) >= 3
        and not _has_compact_exact_values(values)
    ):
        approximate_values = [sp.N(value, 8) for value in values]
        answer = "Tập nghiệm xấp xỉ: {" + "; ".join(sp.sstr(value) for value in approximate_values) + "}"
        answer_latex = r"S \approx \left\{" + ", ".join(sp.latex(value) for value in approximate_values) + r"\right\}"
        return answer, answer_latex
    return format_solution_set(solution_set), sp.latex(solution_set)


def _has_compact_exact_values(values: list[sp.Expr]) -> bool:
    if not values:
        return True
    for value in values:
        if value.has(sp.RootOf):
            return False
        if len(sp.latex(value)) > 48:
            return False
    return True


def _polynomial_degree(expression: sp.Expr, variable: sp.Symbol) -> int | None:
    try:
        return sp.Poly(sp.expand(expression), variable).degree()
    except sp.PolynomialError:
        return None


def _biquadratic_steps(expression: sp.Expr, variable: sp.Symbol, start_index: int) -> list[AlgebraSolveStep]:
    try:
        polynomial = sp.Poly(sp.expand(expression), variable)
    except sp.PolynomialError:
        return []
    if polynomial.degree() != 4:
        return []
    if polynomial.coeff_monomial(variable**3) != 0 or polynomial.coeff_monomial(variable) != 0:
        return []

    t = sp.Symbol("t", real=True)
    a = polynomial.coeff_monomial(variable**4)
    b = polynomial.coeff_monomial(variable**2)
    c = polynomial.coeff_monomial(1)
    t_expression = sp.expand(a * t**2 + b * t + c)
    t_solution_set = sp.solveset(t_expression, t, domain=sp.S.Reals)
    t_values = solution_values(t_solution_set)
    if t_values is None:
        return []
    valid_t_values = [value for value in t_values if sp.simplify(value).is_nonnegative is not False]
    x_values = sorted({root for value in valid_t_values for root in sp.solve(sp.Eq(variable**2, value), variable)}, key=sp.default_sort_key)

    t_lines = [sp.latex(sp.Eq(t_expression, 0, evaluate=False))]
    factored_t = sp.factor(t_expression)
    if factored_t != t_expression:
        t_lines.append(sp.latex(sp.Eq(factored_t, 0, evaluate=False)))
    if t_values:
        t_lines.append(_or_join([rf"{sp.latex(t)}={sp.latex(value)}" for value in t_values]))
    if len(valid_t_values) != len(t_values):
        t_lines.append(rf"{sp.latex(t)}\ge 0")

    back_lines: list[str] = []
    for value in valid_t_values:
        roots = sorted(sp.solve(sp.Eq(variable**2, value), variable), key=sp.default_sort_key)
        back_lines.append(sp.latex(sp.Eq(variable**2, value, evaluate=False)))
        back_lines.append(_or_join([rf"{sp.latex(variable)}={sp.latex(root)}" for root in roots]))
    back_lines.append(r"S=\left\{" + ", ".join(sp.latex(root) for root in x_values) + r"\right\}" if x_values else r"S=\varnothing")

    return [
        AlgebraSolveStep(
            index=start_index,
            title="Đặt ẩn phụ",
            explanation="Các lũy thừa của x đều là x^4, x^2 và hằng số, nên đặt t = x^2 để đưa về phương trình bậc hai.",
            goal="Biến phương trình bậc bốn dạng chẵn thành phương trình bậc hai quen thuộc.",
            why="Vì x^4 = (x^2)^2, đặt t = x^2 làm số mũ giảm từ 4 xuống 2.",
            rule="Đặt t = x^2",
            operation="Thay x^2 bằng t và nhớ điều kiện t >= 0.",
            before_latex=sp.latex(sp.Eq(polynomial.as_expr(), 0, evaluate=False)),
            after_latex=rf"{sp.latex(t)}={sp.latex(variable)}^2,\quad {sp.latex(t)}\ge 0" + "\n" + sp.latex(sp.Eq(t_expression, 0, evaluate=False)),
            pitfall="Không được quên t >= 0 vì t là bình phương của x.",
            check="Thay t = x^2 ngược lại phải thu được phương trình ban đầu.",
            expression=sp.sstr(polynomial.as_expr()),
            expression_latex=sp.latex(sp.Eq(polynomial.as_expr(), 0, evaluate=False)),
            result=sp.sstr(t_expression),
            result_latex=sp.latex(sp.Eq(t_expression, 0, evaluate=False)),
            kind="transform",
            confidence="symbolic",
        ),
        AlgebraSolveStep(
            index=start_index + 1,
            title="Giải phương trình theo ẩn phụ",
            explanation="Giải phương trình bậc hai theo t trước, rồi chỉ giữ các giá trị t không âm.",
            goal="Tìm các giá trị có thể có của x^2.",
            why="Sau khi đặt ẩn phụ, nghiệm của t sẽ cho biết x^2 bằng bao nhiêu.",
            rule="Giải bậc hai theo t",
            operation="Phân tích nhân tử hoặc dùng công thức nghiệm cho phương trình theo t.",
            before_latex=sp.latex(sp.Eq(t_expression, 0, evaluate=False)),
            after_latex="\n".join(t_lines),
            pitfall="Nếu t âm thì không sinh nghiệm thực cho x.",
            check="Mỗi giá trị t giữ lại phải thỏa t >= 0.",
            expression=sp.sstr(t_expression),
            expression_latex=sp.latex(sp.Eq(t_expression, 0, evaluate=False)),
            result="; ".join(sp.sstr(value) for value in valid_t_values),
            result_latex=_or_join([rf"{sp.latex(t)}={sp.latex(value)}" for value in valid_t_values]) if valid_t_values else r"\varnothing",
            kind="solve",
            confidence="symbolic",
        ),
        AlgebraSolveStep(
            index=start_index + 2,
            title="Trả về ẩn ban đầu",
            explanation="Thay từng giá trị của t vào t = x^2 để tìm x.",
            goal="Tìm nghiệm của phương trình theo biến ban đầu.",
            why="Bài toán hỏi x, nên không được dừng ở nghiệm của t.",
            rule="Thay ngược ẩn phụ",
            operation="Giải từng phương trình x^2 = t.",
            before_latex=rf"{sp.latex(t)}={sp.latex(variable)}^2",
            after_latex="\n".join(back_lines),
            pitfall="Với x^2 = a và a > 0 phải lấy cả hai nghiệm x = -sqrt(a) và x = sqrt(a).",
            check="Thay các nghiệm x tìm được vào phương trình gốc.",
            expression="; ".join(sp.sstr(value) for value in valid_t_values),
            result="; ".join(sp.sstr(root) for root in x_values),
            result_latex=r"\left\{" + ", ".join(sp.latex(root) for root in x_values) + r"\right\}" if x_values else r"\varnothing",
            kind="solve",
            confidence="symbolic",
        ),
    ]


def _rational_root_division_steps(expression: sp.Expr, variable: sp.Symbol, start_index: int) -> list[AlgebraSolveStep]:
    try:
        polynomial = sp.Poly(sp.expand(expression), variable)
    except sp.PolynomialError:
        return []
    if polynomial.degree() < 3:
        return []

    divisions: list[tuple[sp.Poly, sp.Expr, sp.Expr]] = []
    current = polynomial
    while current.degree() >= 3:
        root = _first_rational_root(current)
        if root is None:
            break
        quotient, remainder = sp.div(current.as_expr(), variable - root, variable)
        if sp.simplify(remainder) != 0:
            break
        divisions.append((current, root, sp.expand(quotient)))
        current = sp.Poly(sp.expand(quotient), variable)

    if not divisions:
        return []

    first_poly, first_root, _first_quotient = divisions[0]
    candidate_latex = _rational_candidate_latex(first_poly)
    evaluation_latex = _polynomial_evaluation_latex(first_poly, variable, first_root)
    steps = [
        AlgebraSolveStep(
            index=start_index,
            title="Thử nghiệm hữu tỉ",
            explanation="Với đa thức hệ số nguyên, nghiệm hữu tỉ nếu có sẽ nằm trong các ước của hệ số tự do chia cho các ước của hệ số cao nhất.",
            goal="Tìm một nghiệm đơn giản để tách đa thức thành nhân tử.",
            why="Nếu P(r) = 0 thì x - r là một nhân tử của P(x).",
            rule="Định lý nghiệm hữu tỉ",
            operation=f"Thử các nghiệm hữu tỉ ứng viên và chọn r = {sp.sstr(first_root)} vì P(r) = 0.",
            before_latex=sp.latex(sp.Eq(first_poly.as_expr(), 0, evaluate=False)),
            after_latex=(candidate_latex + "\n" if candidate_latex else "") + evaluation_latex + "\n" + sp.latex(sp.Eq(variable, first_root, evaluate=False)),
            pitfall="Không thử ngẫu nhiên; chỉ thử các ứng viên hợp lý để tránh bỏ sót nghiệm hữu tỉ.",
            check="Thay r vào P(x); nếu P(r) bằng 0 thì phép chia cho x - r không có dư.",
            expression=sp.sstr(first_poly.as_expr()),
            expression_latex=sp.latex(first_poly.as_expr()),
            result=sp.sstr(first_root),
            result_latex=sp.latex(sp.Eq(variable, first_root, evaluate=False)),
            kind="transform",
            confidence="symbolic",
        )
    ]

    for offset, (source_poly, root, quotient) in enumerate(divisions, start=1):
        factor = variable - root
        steps.append(AlgebraSolveStep(
            index=start_index + offset,
            title="Chia đa thức",
            explanation=f"Vì {sp.sstr(variable)} = {sp.sstr(root)} là nghiệm, chia đa thức hiện tại cho {sp.sstr(factor)} để hạ bậc.",
            goal="Giảm bậc đa thức để phần còn lại dễ giải hơn.",
            why="P(r) = 0 tương đương P(x) chia hết cho x - r.",
            rule="Chia đa thức cho nhân tử tuyến tính",
            operation=f"Chia {sp.sstr(source_poly.as_expr())} cho {sp.sstr(factor)}.",
            before_latex=sp.latex(source_poly.as_expr()),
            after_latex=rf"\frac{{{sp.latex(source_poly.as_expr())}}}{{{sp.latex(factor)}}}={sp.latex(quotient)}" + "\n" + sp.latex(sp.Eq(source_poly.as_expr(), factor * quotient, evaluate=False)),
            pitfall="Sau phép chia phải kiểm tra dư bằng 0; nếu còn dư thì r không phải nghiệm.",
            check="Nhân ngược nhân tử với thương phải ra đúng đa thức trước khi chia.",
            expression=sp.sstr(source_poly.as_expr()),
            expression_latex=sp.latex(source_poly.as_expr()),
            result=sp.sstr(quotient),
            result_latex=sp.latex(quotient),
            kind="transform",
            confidence="symbolic",
        ))

    factored = sp.factor(polynomial.as_expr())
    final_factor_step = _final_factor_step(polynomial, factored, variable, start_index + len(steps))
    if final_factor_step:
        steps.append(final_factor_step)
    zero_product_step = _zero_product_step(factored, variable, start_index + len(steps))
    if zero_product_step:
        steps.append(zero_product_step)
    return steps


def _first_rational_root(polynomial: sp.Poly) -> sp.Expr | None:
    candidates = _rational_root_candidates(polynomial)
    for candidate in candidates:
        if sp.simplify(polynomial.as_expr().subs(polynomial.gens[0], candidate)) == 0:
            return candidate
    return None


def _rational_root_candidates(polynomial: sp.Poly) -> list[sp.Rational]:
    primitive = sp.Poly(sp.primitive(polynomial.as_expr())[1], polynomial.gens[0])
    leading = int(abs(primitive.LC()))
    constant = int(abs(primitive.TC()))
    if constant == 0:
        return [sp.Rational(0)]
    numerators = sp.divisors(constant)
    denominators = sp.divisors(leading)
    candidates = {sp.Rational(sign * numerator, denominator) for numerator in numerators for denominator in denominators for sign in (1, -1)}
    return sorted(candidates, key=lambda value: (abs(float(value)), float(value)))


def _rational_candidate_latex(polynomial: sp.Poly) -> str | None:
    candidates = _rational_root_candidates(polynomial)
    if len(candidates) > 12:
        return None
    return r"x\in\left\{" + ", ".join(sp.latex(candidate) for candidate in candidates) + r"\right\}"


def _polynomial_evaluation_latex(polynomial: sp.Poly, variable: sp.Symbol, value: sp.Expr) -> str:
    value_latex = sp.latex(value)
    expression_latex = sp.latex(polynomial.as_expr())
    substituted = expression_latex.replace(sp.latex(variable), rf"\left({value_latex}\right)")
    result = sp.simplify(polynomial.as_expr().subs(variable, value))
    return rf"P\left({value_latex}\right)={substituted}={sp.latex(result)}"


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
    zero_product_step = _zero_product_step(factored, variable, start_index + 1)
    if zero_product_step:
        steps.append(zero_product_step)
    return steps


def _final_factor_step(polynomial: sp.Poly, factored: sp.Expr, variable: sp.Symbol, index: int) -> AlgebraSolveStep | None:
    if sp.expand(factored) == factored:
        return None
    return AlgebraSolveStep(
        index=index,
        title="Viết lại thành tích",
        explanation="Ghép các nhân tử đã tách được để đưa phương trình về dạng tích bằng 0.",
        goal="Chuẩn bị áp dụng quy tắc tích bằng 0.",
        why="Khi vế trái là tích các nhân tử, ta có thể giải từng nhân tử riêng.",
        rule="Dạng tích của đa thức",
        operation="Viết đa thức ban đầu dưới dạng tích các nhân tử.",
        before_latex=sp.latex(sp.Eq(polynomial.as_expr(), 0, evaluate=False)),
        after_latex=sp.latex(sp.Eq(factored, 0, evaluate=False)),
        pitfall="Chỉ dùng quy tắc tích bằng 0 khi phương trình đã có vế phải bằng 0.",
        check="Khai triển tích phải thu lại đúng đa thức ban đầu.",
        expression=sp.sstr(polynomial.as_expr()),
        expression_latex=sp.latex(sp.Eq(polynomial.as_expr(), 0, evaluate=False)),
        result=sp.sstr(factored),
        result_latex=sp.latex(sp.Eq(factored, 0, evaluate=False)),
        kind="transform",
        confidence="symbolic",
    )


def _zero_product_step(factored: sp.Expr, variable: sp.Symbol, index: int) -> AlgebraSolveStep | None:
    factor_data = [(base, power) for base, power in sp.factor_list(factored)[1] if base.has(variable)]
    if not factor_data:
        return None

    equations: list[str] = []
    equation_lines: list[str] = []
    roots: list[sp.Expr] = []
    for base, _power in factor_data:
        try:
            factor_poly = sp.Poly(base, variable)
        except sp.PolynomialError:
            return None
        if factor_poly.degree() != 1:
            return None
        root = sp.solve(sp.Eq(base, 0), variable)
        if not root:
            return None
        roots.append(sp.simplify(root[0]))
        equations.append(f"{sp.sstr(base)}=0")
        equation_lines.append(sp.latex(sp.Eq(base, 0, evaluate=False)))
    if not roots:
        return None

    roots = sorted(set(roots), key=sp.default_sort_key)
    root_lines = [rf"{sp.latex(variable)}={sp.latex(root)}" for root in roots]
    return AlgebraSolveStep(
        index=index,
        title="Cho từng nhân tử bằng 0",
        explanation="Vì tích bằng 0 nên cho từng nhân tử bằng 0 rồi giải.",
        goal="Tìm nghiệm của phương trình sau khi đã phân tích nhân tử.",
        why="Một tích bằng 0 khi có ít nhất một thừa số bằng 0.",
        rule="Quy tắc tích bằng 0",
        operation="Giải lần lượt " + "; ".join(equations) + ".",
        before_latex=sp.latex(sp.Eq(factored, 0, evaluate=False)),
        after_latex="\n".join(equation_lines + [r"\Rightarrow " + _or_join(root_lines)]),
        pitfall="Không bỏ sót nhân tử lặp; nhân tử lặp vẫn cho cùng một nghiệm.",
        check="Thay từng nghiệm vào tích đã phân tích để thấy một nhân tử bằng 0.",
        expression="; ".join(equations),
        expression_latex="\n".join(equation_lines),
        result="; ".join(sp.sstr(root) for root in roots),
        result_latex=r"\left\{" + ", ".join(sp.latex(root) for root in roots) + r"\right\}",
        kind="solve",
        confidence="symbolic",
    )


def _or_join(lines: list[str]) -> str:
    return r"\quad\text{hoặc}\quad ".join(lines)


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
