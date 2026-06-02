from app.schemas.algebra import AlgebraSolveRequest
from app.services.algebra import solve_algebra


def test_equation_solver_solves_quadratic():
    result = solve_algebra(AlgebraSolveRequest(input="x^2 - 5*x + 6 = 0"))

    assert result.status == "solved"
    assert result.solution_set.kind == "finite"
    assert {value.text for value in result.solution_set.values} == {"2", "3"}
    assert result.verification.status == "verified"
    assert result.steps
    assert all(step.kind != "normalize" for step in result.steps)
    assert all(step.kind != "domain" for step in result.steps)
    assert result.steps[0].title == "Chọn phương pháp phân tích nhân tử"
    assert result.steps[0].method == "factor"
    assert "Phân tích nhân tử" in [step.title for step in result.steps]
    factor_step = next(step for step in result.steps if step.title == "Cho từng nhân tử bằng 0")
    assert factor_step.rule == "Quy tắc tích bằng 0"
    assert factor_step.check


def test_equation_solver_explains_quadratic_formula_steps():
    result = solve_algebra(AlgebraSolveRequest(input="5x^2+1=2", input_format="latex"))

    assert result.status == "solved"
    titles = [step.title for step in result.steps]
    assert "Đưa về dạng chuẩn bậc hai" in titles
    assert "Tính biệt thức" in titles
    assert "Áp dụng công thức nghiệm" in titles
    root_step = next(step for step in result.steps if step.title == "Áp dụng công thức nghiệm")
    assert root_step.result_latex
    assert "\\sqrt{5}" in root_step.result_latex
    assert root_step.goal
    assert root_step.why
    assert root_step.rule == "Công thức nghiệm bậc hai"
    assert root_step.operation and "Thay a, b" in root_step.operation
    assert root_step.check


def test_equation_solver_explains_depressed_cubic_with_compact_answer():
    result = solve_algebra(AlgebraSolveRequest(input="x^3-5*x+6=0"))

    assert result.status == "solved"
    assert result.answer_latex == r"S \approx \left\{-2.6890953\right\}"
    titles = [step.title for step in result.steps]
    assert "Đưa về dạng bậc ba Cardano" in titles
    assert "Tính biệt thức Cardano" in titles
    assert "Áp dụng công thức Cardano" in titles
    root_step = next(step for step in result.steps if step.title == "Áp dụng công thức Cardano")
    assert root_step.result_latex
    assert "\\sqrt[3]" in root_step.result_latex


def test_equation_solver_reports_empty_solution_set():
    result = solve_algebra(AlgebraSolveRequest(input="1/(x-1)=0"))

    assert result.status == "solved"
    assert result.solution_set.kind == "empty"
    assert "Vô nghiệm" in result.answer
    assert any("x - 1" in assumption for assumption in result.assumptions)
    domain_step = next(step for step in result.steps if step.kind == "domain")
    assert domain_step.why
    assert domain_step.pitfall and "bỏ qua điều kiện" in domain_step.pitfall
    rational_step = next(step for step in result.steps if step.title == "Quy đồng và khử mẫu")
    assert rational_step.rule == "Khử mẫu phân thức"
    assert rational_step.check and "khác 0" in rational_step.check


def test_equation_solver_filters_extraneous_sqrt_solution():
    result = solve_algebra(AlgebraSolveRequest(input="sqrt(x+1)=x-1"))

    assert result.status == "solved"
    assert {value.text for value in result.solution_set.values} == {"3"}
    assert result.verification.status == "verified"
    titles = [step.title for step in result.steps]
    assert titles[0] == "Chọn phương pháp xử lý căn"
    assert titles[1:4] == ["Điều kiện căn thức", "Cô lập căn", "Bình phương hai vế"]
    filter_step = next(step for step in result.steps if step.title == "Lọc nghiệm ngoại lai")
    assert filter_step.why
    assert filter_step.rule == "Thử lại nghiệm sau bình phương"
    assert filter_step.check
    assert "x=0" in filter_step.after_latex
    assert "\\text{loại}" in filter_step.after_latex
    square_step = next(step for step in result.steps if step.title == "Bình phương hai vế")
    assert square_step.pitfall and "Bình phương" in square_step.pitfall


def test_equation_solver_splits_factored_denominator_assumptions():
    result = solve_algebra(AlgebraSolveRequest(input="1/((x-1)*(x+2))=0"))

    assert "x - 1 khác 0" in result.assumptions
    assert "x + 2 khác 0" in result.assumptions


def test_equation_solver_keeps_original_rational_domain_after_simplification():
    result = solve_algebra(AlgebraSolveRequest(input="(x^2-1)/(x-1)=0"))

    assert result.status == "solved"
    assert {value.text for value in result.solution_set.values} == {"-1"}
    assert "x - 1 khác 0" in result.assumptions
    titles = [step.title for step in result.steps]
    assert "Quy đồng và khử mẫu" in titles
    assert "Lọc nghiệm theo điều kiện gốc" in titles
    zero_product_step = next(step for step in result.steps if step.title == "Cho từng nhân tử bằng 0")
    assert "x=1" in zero_product_step.after_latex
    filter_step = next(step for step in result.steps if step.title == "Lọc nghiệm theo điều kiện gốc")
    assert filter_step.result_latex == r"\left\{-1\right\}"


def test_equation_solver_explains_cubic_by_rational_root_and_division():
    result = solve_algebra(AlgebraSolveRequest(input="x^3 - 6*x^2 + 11*x - 6 = 0"))

    assert result.status == "solved"
    assert {value.text for value in result.solution_set.values} == {"1", "2", "3"}
    assert result.answer_latex == r"\left\{1, 2, 3\right\}"
    titles = [step.title for step in result.steps]
    assert "Thử nghiệm hữu tỉ" in titles
    assert "Chia đa thức" in titles
    assert "Viết lại thành tích" in titles
    zero_product_step = next(step for step in result.steps if step.title == "Cho từng nhân tử bằng 0")
    assert zero_product_step.after_latex
    assert "\n" in zero_product_step.after_latex
    assert "\\quadx" not in zero_product_step.after_latex


def test_equation_solver_explains_biquadratic_substitution():
    result = solve_algebra(AlgebraSolveRequest(input="x^4 - 5*x^2 + 4 = 0"))

    assert result.status == "solved"
    assert {value.text for value in result.solution_set.values} == {"-2", "-1", "1", "2"}
    titles = [step.title for step in result.steps]
    assert titles[0] == "Chọn phương pháp đặt ẩn phụ"
    assert titles[1:4] == ["Đặt ẩn phụ", "Giải phương trình theo ẩn phụ", "Trả về ẩn ban đầu"]
    substitution_step = next(step for step in result.steps if step.title == "Đặt ẩn phụ")
    assert "t=x^2" in substitution_step.after_latex
    back_step = next(step for step in result.steps if step.title == "Trả về ẩn ban đầu")
    assert "x^{2} = 1" in back_step.after_latex
    assert "\\quadx" not in back_step.after_latex


def test_equation_solver_explains_double_radical_by_two_squarings():
    result = solve_algebra(AlgebraSolveRequest(input="sqrt(x+1)+sqrt(x-2)=3"))

    assert result.status == "solved"
    assert {value.text for value in result.solution_set.values} == {"3"}
    titles = [step.title for step in result.steps]
    assert titles[0] == "Chọn phương pháp xử lý căn"
    assert titles[1:7] == [
        "Điều kiện căn thức",
        "Cô lập căn thứ nhất",
        "Bình phương lần một",
        "Cô lập căn còn lại",
        "Bình phương lần hai",
        "Giải phương trình sau bình phương",
    ]
    first_square = next(step for step in result.steps if step.title == "Bình phương lần một")
    assert "\\sqrt{x - 2}" in first_square.after_latex
    second_square = next(step for step in result.steps if step.title == "Bình phương lần hai")
    assert "\\sqrt" not in second_square.after_latex
    filter_step = next(step for step in result.steps if step.title == "Lọc nghiệm ngoại lai")
    assert "S=\\left\\{3\\right\\}" in filter_step.after_latex
