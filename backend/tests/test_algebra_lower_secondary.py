import pytest

from app.schemas.algebra import AlgebraSolveRequest
from app.services.algebra.interpreter import interpret_algebra_input
from app.services.algebra.service import solve_algebra
from app.services.math_solution_projectors import project_algebra_solution


def test_lower_secondary_gcd_and_lcm_from_vietnamese_input():
    gcd_result = solve_algebra(AlgebraSolveRequest(input="Tính UCLN của 18 và 24"))
    lcm_result = solve_algebra(AlgebraSolveRequest(input="Tính BCNN của 12, 18 và 30"))

    assert gcd_result.status == "solved"
    assert gcd_result.topic == "arithmetic"
    assert gcd_result.problem_type == "gcd"
    assert gcd_result.solution_set.text == "6"
    assert gcd_result.verification.status == "verified"

    assert lcm_result.status == "solved"
    assert lcm_result.problem_type == "lcm"
    assert lcm_result.solution_set.text == "180"
    assert lcm_result.verification.checks[0].name == "lcm_divisibility"


def test_lower_secondary_percent_and_ratio_use_exact_arithmetic():
    percent = solve_algebra(AlgebraSolveRequest(input="12,5 phần trăm của 240"))
    percent_ratio = solve_algebra(AlgebraSolveRequest(input="20 là bao nhiêu phần trăm của 80"))
    percent_base = solve_algebra(AlgebraSolveRequest(input="25% của số đó bằng 50"))
    ratio = solve_algebra(AlgebraSolveRequest(input="Rút gọn tỉ lệ 18:24"))

    assert percent.status == "solved"
    assert percent.problem_type == "percent"
    assert percent.solution_set.text == "30"
    assert percent.answer_latex == "30"

    assert percent_ratio.status == "solved"
    assert percent_ratio.problem_type == "percent_ratio"
    assert percent_ratio.solution_set.text == "25%"
    assert percent_ratio.verification.checks[0].name == "percent_ratio_identity"

    assert percent_base.status == "solved"
    assert percent_base.problem_type == "percent_base"
    assert percent_base.solution_set.text == "200"
    assert percent_base.verification.checks[0].name == "percent_base_identity"

    assert ratio.status == "solved"
    assert ratio.problem_type == "ratio"
    assert ratio.solution_set.text == "3:4"
    assert ratio.verification.checks[0].name == "ratio_cross_product"


def test_arithmetic_parser_and_solution_ir_stay_inside_ratio_percent_skill():
    request = AlgebraSolveRequest(input="20 là bao nhiêu phần trăm của 80")
    interpretation = interpret_algebra_input(request)
    response = solve_algebra(request)
    projected = project_algebra_solution(request, response)

    assert interpretation.canonical_input == "percent_ratio(part=20,whole=80)"
    assert interpretation.variables == []
    assert projected.problem.curriculum.skill_ids == ["number.ratio_percent"]
    assert projected.capability.skill_ids == ["number.ratio_percent"]


def test_lower_secondary_fraction_expression_stays_exact():
    result = solve_algebra(AlgebraSolveRequest(input="3/4 + 2/3"))

    assert result.status == "solved"
    assert result.topic == "expression"
    assert result.solution_set.text == "17/12"
    assert result.verification.status == "verified"


@pytest.mark.parametrize(("text", "action", "expected", "problem_type"), [
    ("Khai triển biểu thức (x + 1)^2", "expand", "x**2 + 2*x + 1", "transform_expand"),
    ("Khai triển biểu thức x^2 - 1", "expand", "x**2 - 1", "transform_expand"),
    ("Phân tích đa thức x^2 - 1 thành nhân tử", "factor", "(x - 1)*(x + 1)", "transform_factor"),
    ("Thu gọn biểu thức 2*x + 3*x - 4", "simplify", "5*x - 4", "transform_simplify"),
])
def test_expression_instruction_controls_deterministic_transformation(
    text: str,
    action: str,
    expected: str,
    problem_type: str,
):
    request = AlgebraSolveRequest(input=text)
    interpretation = interpret_algebra_input(request)
    result = solve_algebra(request)

    assert interpretation.topic_hint == "expression"
    assert interpretation.expression_action == action
    assert result.status == "solved"
    assert result.problem_type == problem_type
    assert result.solution_set.text == expected
    assert result.verification.checks[0].name == "symbolic_equivalence"
    assert result.verification.status == "verified"


def test_expression_solution_ir_uses_operation_specific_skills():
    simplify_request = AlgebraSolveRequest(input="Thu gọn biểu thức 2*x + 3*x")
    factor_request = AlgebraSolveRequest(input="Phân tích đa thức x^2 - 1 thành nhân tử")

    simplify_ir = project_algebra_solution(simplify_request, solve_algebra(simplify_request))
    factor_ir = project_algebra_solution(factor_request, solve_algebra(factor_request))

    assert simplify_ir.problem.curriculum.skill_ids == ["algebra.expression_transform"]
    assert factor_ir.problem.curriculum.skill_ids == [
        "algebra.expression_transform",
        "algebra.polynomial_operations",
    ]


@pytest.mark.parametrize(("problem", "topic", "expected"), [
    ("2*x + 3*x - 4", "expression", "5*x - 4"),
    ("x^2 - 5*x + 6", "expression", "(x - 3)*(x - 2)"),
    ("sqrt(50)", "expression", "5*sqrt(2)"),
    ("Giải phương trình 2x + 3 = 11", "equation", "4"),
    ("Giải bất phương trình 3x - 2 > 7", "inequality", "(3; +∞)"),
    ("x+y=5; x-y=1", "system", "x = 3; y = 2"),
])
def test_lower_secondary_algebra_vertical_slice(problem: str, topic: str, expected: str):
    result = solve_algebra(AlgebraSolveRequest(input=problem))

    assert result.status == "solved"
    assert result.topic == topic
    assert expected in result.solution_set.text
    assert result.verification.status in {"verified", "partially_verified"}


def test_lower_secondary_power_and_divisibility_have_typed_verifiers():
    power = solve_algebra(AlgebraSolveRequest(input="Tính lũy thừa 2 mũ 5"))
    divisible = solve_algebra(AlgebraSolveRequest(input="Kiểm tra 84 có chia hết cho 7 không"))
    not_divisible = solve_algebra(AlgebraSolveRequest(input="Kiểm tra 85 có chia hết cho 7 không"))

    assert power.problem_type == "power"
    assert power.solution_set.text == "32"
    assert power.verification.checks[0].name == "power_repeated_multiplication"
    assert divisible.problem_type == "divisible"
    assert divisible.solution_set.text == "ĐÚNG"
    assert not_divisible.solution_set.text == "SAI"
    assert not_divisible.verification.status == "verified"


def test_typed_word_problems_preserve_units_and_multi_step_order():
    one_step = solve_algebra(AlgebraSolveRequest(input="Lan có 24 quyển vở, cho bạn 6 quyển. Lan còn lại bao nhiêu quyển vở?"))
    multi_step = solve_algebra(AlgebraSolveRequest(input="Một cửa hàng có 120 kg gạo, bán 35 kg rồi nhập thêm 20 kg. Hiện có bao nhiêu kg gạo?"))
    product = solve_algebra(AlgebraSolveRequest(input="Có 6 hộp, mỗi hộp 8 bút. Có tất cả bao nhiêu bút?"))
    share = solve_algebra(AlgebraSolveRequest(input="Có 48 cái kẹo chia đều cho 6 bạn, mỗi bạn được bao nhiêu cái kẹo?"))

    assert one_step.solution_set.text == "18 quyen vo"
    assert one_step.verification.checks[0].name == "word_problem_recompute"
    assert multi_step.solution_set.text == "105 kg gao"
    assert len(multi_step.steps) == 3
    assert [step.title for step in multi_step.steps[:2]] == ["Bớt số lượng", "Cộng thêm số lượng"]
    assert product.solution_set.text == "48 but"
    assert share.solution_set.text == "8 cai keo"
    assert all(result.status == "solved" for result in (one_step, multi_step, product, share))


def test_word_problem_solution_ir_maps_to_number_skill_without_fake_variable():
    request = AlgebraSolveRequest(input="Một cửa hàng có 120 kg gạo, bán 35 kg rồi nhập thêm 20 kg. Hiện có bao nhiêu kg gạo?")
    interpretation = interpret_algebra_input(request)
    response = solve_algebra(request)
    projected = project_algebra_solution(request, response)

    assert interpretation.topic_hint == "arithmetic"
    assert interpretation.variables == []
    assert interpretation.canonical_input == "word_inventory(start=120,unit=kg_gao;steps=sub:35|add:20)"
    assert projected.problem.curriculum.skill_ids == ["number.integer_arithmetic"]
    assert projected.status == "solved_verified"


def test_word_problem_rejects_negative_inventory_and_zero_share_groups():
    negative = solve_algebra(AlgebraSolveRequest(input="Lan có 4 quyển vở, cho bạn 6 quyển. Lan còn lại bao nhiêu quyển vở?"))
    zero_groups = solve_algebra(AlgebraSolveRequest(input="Có 48 cái kẹo chia đều cho 0 bạn, mỗi bạn được bao nhiêu cái kẹo?"))

    assert negative.status == "unsupported"
    assert "âm" in negative.answer
    assert zero_groups.status == "unsupported"
    assert "phải dương" in zero_groups.answer


def test_lower_secondary_arithmetic_rejects_invalid_boundaries():
    zero_ratio = solve_algebra(AlgebraSolveRequest(input="Rút gọn tỉ lệ 3:0"))
    zero_percent_whole = solve_algebra(AlgebraSolveRequest(input="3 là bao nhiêu phần trăm của 0"))
    zero_percent_rate = solve_algebra(AlgebraSolveRequest(input="0% của số đó bằng 3"))
    zero_lcm = solve_algebra(AlgebraSolveRequest(input="BCNN của 0 và 12"))

    assert zero_ratio.status == "unsupported"
    assert "không được bằng 0" in zero_ratio.answer
    assert zero_percent_whole.status == "unsupported"
    assert "toàn phần phải khác 0" in zero_percent_whole.answer
    assert zero_percent_rate.status == "unsupported"
    assert "phần trăm phải khác 0" in zero_percent_rate.answer
    assert zero_lcm.status == "unsupported"
    assert "khác 0" in zero_lcm.answer


def test_power_divisibility_and_word_units_reject_invalid_boundaries():
    negative_exponent = solve_algebra(AlgebraSolveRequest(input="Tính lũy thừa 2 mũ -1"))
    excessive_exponent = solve_algebra(AlgebraSolveRequest(input="Tính lũy thừa 2 mũ 21"))
    zero_divisor = solve_algebra(AlgebraSolveRequest(input="Kiểm tra 84 có chia hết cho 0 không"))
    unit_mismatch = solve_algebra(
        AlgebraSolveRequest(input="Lan có 24 quyển vở, cho bạn 6 bút. Lan còn lại bao nhiêu quyển vở?")
    )

    assert negative_exponent.status == "unsupported"
    assert "không âm" in negative_exponent.answer
    assert excessive_exponent.status == "unsupported"
    assert "giới hạn" in excessive_exponent.answer
    assert zero_divisor.status == "unsupported"
    assert "khác 0" in zero_divisor.answer
    assert unit_mismatch.status != "solved"


def test_absolute_value_and_radical_have_exact_skill_evidence():
    absolute_request = AlgebraSolveRequest(input="Giải phương trình Abs(x - 2) = 3")
    radical_request = AlgebraSolveRequest(input="Rút gọn biểu thức sqrt(50)")
    absolute = solve_algebra(absolute_request)
    radical = solve_algebra(radical_request)

    assert absolute.status == "solved"
    assert absolute.solution_set.text == "Tập nghiệm: {-1; 5}"
    assert absolute.verification.status == "verified"
    assert radical.status == "solved"
    assert radical.solution_set.text == "5*sqrt(2)"
    assert radical.verification.status == "verified"
    assert interpret_algebra_input(radical_request).variables == []
    assert project_algebra_solution(absolute_request, absolute).problem.curriculum.skill_ids == [
        "algebra.absolute_radical"
    ]
    assert project_algebra_solution(radical_request, radical).problem.curriculum.skill_ids == [
        "algebra.absolute_radical"
    ]