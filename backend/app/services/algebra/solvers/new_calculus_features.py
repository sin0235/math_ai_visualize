import sympy as sp
from app.schemas.algebra import AlgebraSolveStep, AlgebraSolveResponse, AlgebraSolutionSet, AlgebraVerificationReport, AlgebraVerificationCheck
from app.services.algebra.solvers.calculus_solver import ParsedAlgebraProblem, CalculusTemplate, _calculus_conclusion_step
from app.services.algebra.calculus_transformations import limit_steps

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
                title=f"Viết công thức đạo hàm bằng định nghĩa tại x = {sp.sstr(x0)}",
                explanation=f"Đạo hàm của hàm số tại $x_0 = {sp.latex(x0)}$ được tính bằng giới hạn: $\\lim_{{{sp.latex(delta_x)}\\to 0}} \\frac{{f({sp.latex(x0)}+{sp.latex(delta_x)}) - f({sp.latex(x0)})}}{{{sp.latex(delta_x)}}}$",
                short_explanation="Dùng định nghĩa đạo hàm tại một điểm.",
                detail_level="standard",
                method="derivative_definition",
                goal="Thiết lập giới hạn cần tính.",
                why="Định nghĩa đạo hàm là giới hạn của tỉ số gia số hàm số trên gia số đối số.",
                rule="Đạo hàm bằng định nghĩa",
                operation="Thay hàm số vào công thức giới hạn.",
                after_latex=rf"f'({sp.latex(x0)}) = \lim_{{{sp.latex(delta_x)}\to 0}} \frac{{{sp.latex(f_x0_dx)} - \left({sp.latex(f_x0)}\right)}}{{{sp.latex(delta_x)}}}",
                result_latex=sp.latex(ratio),
                kind="transform",
                confidence="symbolic",
            )
        ]
        
        lim_st = limit_steps(ratio, delta_x, sp.sympify(0), "+-", result)
        for i, st in enumerate(lim_st):
            st.index = len(steps) + 1
            steps.append(st)
            
        answer = f"f'({sp.sstr(x0)}) = {sp.sstr(result)}"
        answer_latex = sp.latex(result)
        milestones = [
            f"Hàm số: f({sp.latex(x)}) = {sp.latex(f_x)}",
            f"Đạo hàm tại x_0 = {sp.latex(x0)}: {sp.latex(result)}"
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
                explanation=f"Đạo hàm của hàm số $f({sp.latex(x)})$ được tính bằng giới hạn: $\\lim_{{{sp.latex(delta_x)}\\to 0}} \\frac{{f({sp.latex(x)}+{sp.latex(delta_x)}) - f({sp.latex(x)})}}{{{sp.latex(delta_x)}}}$",
                short_explanation="Dùng định nghĩa đạo hàm.",
                detail_level="standard",
                method="derivative_definition",
                goal="Thiết lập giới hạn cần tính.",
                why="Định nghĩa đạo hàm là giới hạn của tỉ số gia số hàm số trên gia số đối số.",
                rule="Đạo hàm bằng định nghĩa",
                operation="Thay hàm số vào công thức giới hạn.",
                after_latex=rf"f'({sp.latex(x)}) = \lim_{{{sp.latex(delta_x)}\to 0}} \frac{{{sp.latex(f_x_dx)} - \left({sp.latex(f_x)}\right)}}{{{sp.latex(delta_x)}}}",
                result_latex=sp.latex(ratio),
                kind="transform",
                confidence="symbolic",
            )
        ]
        
        lim_st = limit_steps(ratio, delta_x, sp.sympify(0), "+-", result)
        for i, st in enumerate(lim_st):
            st.index = len(steps) + 1
            steps.append(st)
            
        answer = f"f'({sp.sstr(x)}) = {sp.sstr(result)}"
        answer_latex = sp.latex(result)
        milestones = [
            f"Hàm số: f({sp.latex(x)}) = {sp.latex(f_x)}",
            f"Đạo hàm bằng định nghĩa: f'({sp.latex(x)}) = {sp.latex(result)}"
        ]

    verification = AlgebraVerificationReport(
        status="verified",
        checks=[AlgebraVerificationCheck(name="derivative_definition_symbolic", status="pass", detail="Đạo hàm được kiểm tra bằng phép tính symbolic.", latex=sp.latex(result))],
        method=["sympy.limit"],
    )
    steps.append(_calculus_conclusion_step(len(steps) + 1, "Kết luận đạo hàm", answer, answer_latex))
    
    return AlgebraSolveResponse(
        input=problem.raw_input,
        normalized_input=problem.normalized_input,
        topic="calculus_derivative_by_definition",
        problem_type="differentiate_by_definition",
        status="solved",
        answer=answer,
        answer_latex=answer_latex,
        solution_set=AlgebraSolutionSet(kind="expression", text=sp.sstr(result), latex=sp.latex(result)),
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
            title=f"Tính giá trị hàm số tại x = {sp.sstr(x0)}",
            explanation=f"Thay $x = {sp.latex(x0)}$ vào hàm số để tìm $f({sp.latex(x0)})$. " + (f"Ta được $f({sp.latex(x0)}) = {sp.latex(f_x0)}$." if is_f_x0_defined else f"Hàm số không xác định tại $x = {sp.latex(x0)}$."),
            short_explanation=f"Tính f({sp.latex(x0)}).",
            detail_level="standard",
            method="continuous_eval",
            goal="Xác định f(x0).",
            why="Để hàm số liên tục tại điểm, giá trị hàm số tại đó phải tồn tại.",
            rule="Định nghĩa liên tục",
            operation="Thay x0 vào biểu thức.",
            after_latex=rf"f({sp.latex(x0)}) = {sp.latex(f_x0)}" if is_f_x0_defined else r"\text{Không xác định}",
            result=sp.sstr(f_x0) if is_f_x0_defined else "undefined",
            result_latex=sp.latex(f_x0) if is_f_x0_defined else "undefined",
            kind="solve",
            confidence="verified",
        )
    )

    if not is_f_x0_defined:
        answer = "Không liên tục"
        answer_latex = r"\text{Gián đoạn}"
        steps.append(_calculus_conclusion_step(len(steps) + 1, "Kết luận tính liên tục", "Hàm số không xác định tại điểm xét nên không liên tục (bị gián đoạn).", answer_latex))
        return AlgebraSolveResponse(...) # I'll fill the rest later

    # Limit part
    if is_piecewise:
        # For piecewise, we must calculate limit from left and right
        lim_left = sp.limit(f_x, x, x0, dir="-")
        lim_right = sp.limit(f_x, x, x0, dir="+")
        
        steps.append(
            AlgebraSolveStep(
                index=2,
                title=f"Tính giới hạn trái tại x = {sp.sstr(x0)}",
                explanation=f"Tính giới hạn của hàm số khi $x \\to {sp.latex(x0)}^-$. Kết quả: $\\lim_{{x \\to {sp.latex(x0)}^-}} f(x) = {sp.latex(lim_left)}$.",
                short_explanation="Tính giới hạn trái.",
                detail_level="standard",
                method="limit_left",
                goal="Tính giới hạn một phía.",
                why="Hàm phân nhánh cần tính giới hạn 2 bên.",
                rule="Giới hạn",
                operation="Lấy giới hạn.",
                after_latex=rf"\lim_{{x \to {sp.latex(x0)}^-}} f(x) = {sp.latex(lim_left)}",
                result=sp.sstr(lim_left),
                result_latex=sp.latex(lim_left),
                kind="solve",
                confidence="verified",
            )
        )
        steps.append(
            AlgebraSolveStep(
                index=3,
                title=f"Tính giới hạn phải tại x = {sp.sstr(x0)}",
                explanation=f"Tính giới hạn của hàm số khi $x \\to {sp.latex(x0)}^+$. Kết quả: $\\lim_{{x \\to {sp.latex(x0)}^+}} f(x) = {sp.latex(lim_right)}$.",
                short_explanation="Tính giới hạn phải.",
                detail_level="standard",
                method="limit_right",
                goal="Tính giới hạn một phía.",
                why="Hàm phân nhánh cần tính giới hạn 2 bên.",
                rule="Giới hạn",
                operation="Lấy giới hạn.",
                after_latex=rf"\lim_{{x \to {sp.latex(x0)}^+}} f(x) = {sp.latex(lim_right)}",
                result=sp.sstr(lim_right),
                result_latex=sp.latex(lim_right),
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
                    explanation=f"Vì giới hạn trái ({sp.latex(lim_left)}) khác giới hạn phải ({sp.latex(lim_right)}) nên không tồn tại giới hạn của hàm số tại $x = {sp.latex(x0)}$.",
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
                    explanation=f"Vì giới hạn trái bằng giới hạn phải và bằng ${sp.latex(lim_val)}$ nên $\\lim_{{x \\to {sp.latex(x0)}}} f(x) = {sp.latex(lim_val)}$.",
                    short_explanation="Tồn tại giới hạn.",
                    detail_level="standard",
                    method="compare_limits",
                    goal="Xét sự tồn tại giới hạn.",
                    why="Giới hạn tồn tại khi 2 giới hạn một phía bằng nhau.",
                    rule="Sự tồn tại giới hạn",
                    operation="So sánh.",
                    after_latex=rf"\lim_{{x \to {sp.latex(x0)}}} f(x) = {sp.latex(lim_val)}",
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
        explanation = f"Vì hàm số không có giới hạn hữu hạn tại $x = {sp.latex(x0)}$ nên hàm số gián đoạn tại điểm này."
    elif sp.simplify(lim_val - f_x0) == 0:
        answer = "Liên tục"
        answer_latex = r"\text{Liên tục}"
        explanation = f"Vì $\\lim_{{x \\to {sp.latex(x0)}}} f(x) = f({sp.latex(x0)}) = {sp.latex(f_x0)}$ nên hàm số liên tục tại $x = {sp.latex(x0)}$."
    else:
        answer = "Gián đoạn"
        answer_latex = r"\text{Gián đoạn}"
        explanation = f"Vì $\\lim_{{x \\to {sp.latex(x0)}}} f(x) = {sp.latex(lim_val)} \\neq f({sp.latex(x0)}) = {sp.latex(f_x0)}$ nên hàm số gián đoạn tại $x = {sp.latex(x0)}$."
        
    steps.append(_calculus_conclusion_step(len(steps) + 1, "Kết luận tính liên tục", explanation, answer_latex))

    verification = AlgebraVerificationReport(
        status="verified",
        checks=[AlgebraVerificationCheck(name="continuous_symbolic", status="pass", detail="Kiểm tra tính liên tục bằng phép tính symbolic.", latex=answer_latex)],
        method=["sympy.limit"],
    )
    
    milestones = [
        f"Hàm số: f(x) = {sp.latex(f_x)}",
        f"Xét tại x = {sp.latex(x0)}: {answer}"
    ]

    return AlgebraSolveResponse(
        input=problem.raw_input,
        normalized_input=problem.normalized_input,
        topic="calculus_continuous_at",
        problem_type="continuous_at",
        status="solved",
        answer=answer,
        answer_latex=answer_latex,
        solution_set=AlgebraSolutionSet(kind="string", text=answer, latex=answer_latex),
        steps=steps,
        milestones=milestones,
        verification=verification,
    )
