from __future__ import annotations

import math
import re
from fractions import Fraction
from functools import reduce

from app.schemas.algebra import (
    AlgebraSolutionSet,
    AlgebraSolveResponse,
    AlgebraSolveStep,
    AlgebraVerificationCheck,
    AlgebraVerificationReport,
)
from app.services.algebra.parser import ParsedAlgebraProblem
from app.services.algebra.steps import conclusion_step


_INTEGER_LIST_RE = re.compile(r"^(gcd|lcm)\((-?\d+(?:,-?\d+){1,7})\)$")
_POWER_RE = re.compile(r"^power\((-?\d+),(-?\d+)\)$")
_DIVISIBLE_RE = re.compile(r"^divisible\((-?\d+),(-?\d+)\)$")
_PERCENT_RE = re.compile(r"^percent\(rate=([-+]?\d+(?:\.\d+)?),value=([-+]?\d+(?:\.\d+)?)\)$")
_PERCENT_RATIO_RE = re.compile(r"^percent_ratio\(part=([-+]?\d+(?:\.\d+)?),whole=([-+]?\d+(?:\.\d+)?)\)$")
_PERCENT_BASE_RE = re.compile(r"^percent_base\(rate=([-+]?\d+(?:\.\d+)?),part=([-+]?\d+(?:\.\d+)?)\)$")
_RATIO_RE = re.compile(r"^ratio\((-?\d+),(-?\d+)\)$")
_WORD_INVENTORY_RE = re.compile(
    r"^word_inventory\(start=([-+]?\d+(?:\.\d+)?),unit=([a-z_]+);steps=((?:add|sub):[-+]?\d+(?:\.\d+)?(?:\|(?:add|sub):[-+]?\d+(?:\.\d+)?)*)\)$"
)
_WORD_PRODUCT_RE = re.compile(
    r"^word_product\(groups=([-+]?\d+(?:\.\d+)?),size=([-+]?\d+(?:\.\d+)?),unit=([a-z_]+)\)$"
)
_WORD_SHARE_RE = re.compile(
    r"^word_share\(total=([-+]?\d+(?:\.\d+)?),groups=([-+]?\d+(?:\.\d+)?),unit=([a-z_]+)\)$"
)


def solve_arithmetic(problem: ParsedAlgebraProblem) -> AlgebraSolveResponse:
    text = problem.normalized_input.replace(" ", "")
    integer_match = _INTEGER_LIST_RE.fullmatch(text)
    if integer_match:
        operation, raw_values = integer_match.groups()
        values = [int(value) for value in raw_values.split(",")]
        return _solve_gcd_lcm(problem, operation, values)

    power_match = _POWER_RE.fullmatch(text)
    if power_match:
        return _solve_power(problem, int(power_match.group(1)), int(power_match.group(2)))

    divisible_match = _DIVISIBLE_RE.fullmatch(text)
    if divisible_match:
        return _solve_divisibility(problem, int(divisible_match.group(1)), int(divisible_match.group(2)))

    percent_match = _PERCENT_RE.fullmatch(text)
    if percent_match:
        rate, value = (Fraction(raw) for raw in percent_match.groups())
        return _solve_percent(problem, rate, value)

    percent_ratio_match = _PERCENT_RATIO_RE.fullmatch(text)
    if percent_ratio_match:
        part, whole = (Fraction(raw) for raw in percent_ratio_match.groups())
        return _solve_percent_ratio(problem, part, whole)

    percent_base_match = _PERCENT_BASE_RE.fullmatch(text)
    if percent_base_match:
        rate, part = (Fraction(raw) for raw in percent_base_match.groups())
        return _solve_percent_base(problem, rate, part)

    ratio_match = _RATIO_RE.fullmatch(text)
    if ratio_match:
        left, right = (int(raw) for raw in ratio_match.groups())
        return _solve_ratio(problem, left, right)

    inventory_match = _WORD_INVENTORY_RE.fullmatch(text)
    if inventory_match:
        start, unit, raw_steps = inventory_match.groups()
        steps = [(operation, Fraction(value)) for operation, value in re.findall(r"(add|sub):([-+]?\d+(?:\.\d+)?)", raw_steps)]
        return _solve_word_inventory(problem, Fraction(start), unit, steps)

    product_match = _WORD_PRODUCT_RE.fullmatch(text)
    if product_match:
        groups, size, unit = product_match.groups()
        return _solve_word_product(problem, Fraction(groups), Fraction(size), unit)

    share_match = _WORD_SHARE_RE.fullmatch(text)
    if share_match:
        total, groups, unit = share_match.groups()
        return _solve_word_share(problem, Fraction(total), Fraction(groups), unit)

    return _unsupported(problem, "Dạng số học chưa được nhận diện.")


def _solve_power(problem: ParsedAlgebraProblem, base: int, exponent: int) -> AlgebraSolveResponse:
    if exponent < 0:
        return _unsupported(problem, "Số mũ phải là số nguyên không âm trong phạm vi THCS.")
    if exponent > 20:
        return _unsupported(problem, "Số mũ vượt giới hạn THCS là 20.")
    result = base ** exponent
    verification_passed = exponent == 0 or result == math.prod([base] * exponent)
    return _response(
        problem,
        problem_type="power",
        title="Tính lũy thừa",
        explanation="Nhân cơ số với chính nó số lần bằng số mũ.",
        rule="a^n là tích của n thừa số a",
        before=f"{base}^{exponent}",
        result=str(result),
        result_latex=str(result),
        verification_name="power_repeated_multiplication",
        verification_passed=verification_passed,
        verification_detail="Tính lại bằng phép nhân lặp độc lập.",
    )


def _solve_divisibility(problem: ParsedAlgebraProblem, value: int, divisor: int) -> AlgebraSolveResponse:
    if divisor == 0:
        return _unsupported(problem, "Số chia phải khác 0 khi kiểm tra chia hết.")
    remainder = value % divisor
    result = "ĐÚNG" if remainder == 0 else "SAI"
    return _response(
        problem,
        problem_type="divisible",
        title="Kiểm tra tính chia hết",
        explanation="Tính số dư của phép chia.",
        rule="a chia hết cho b khi a mod b = 0",
        before=f"{value} mod {divisor}",
        result=result,
        result_latex=result,
        verification_name="divisibility_remainder",
        verification_passed=((remainder == 0) == (result == "ĐÚNG")),
        verification_detail=f"Số dư bằng {remainder}.",
    )


def _solve_gcd_lcm(problem: ParsedAlgebraProblem, operation: str, values: list[int]) -> AlgebraSolveResponse:
    if not any(values):
        return _unsupported(problem, "UCLN/BCNN của toàn số 0 không xác định trong phạm vi này.")
    absolute_values = [abs(value) for value in values]
    if operation == "lcm" and any(value == 0 for value in absolute_values):
        return _unsupported(problem, "BCNN yêu cầu các số nguyên khác 0 trong phạm vi THCS.")
    if operation == "gcd":
        result = reduce(math.gcd, absolute_values)
        title = "Tính ước chung lớn nhất"
        rule = "UCLN"
        verification_passed = all(value % result == 0 for value in absolute_values if value)
        detail = "Kết quả chia hết mọi số đầu vào."
    else:
        result = reduce(math.lcm, absolute_values)
        title = "Tính bội chung nhỏ nhất"
        rule = "BCNN"
        verification_passed = result > 0 and all(result % value == 0 for value in absolute_values if value)
        detail = "Kết quả là bội của mọi số đầu vào."
    return _response(
        problem,
        problem_type=operation,
        title=title,
        explanation=f"Áp dụng thuật toán Euclid cho {', '.join(map(str, values))}.",
        rule=rule,
        before=", ".join(map(str, values)),
        result=str(result),
        result_latex=str(result),
        verification_name=f"{operation}_divisibility",
        verification_passed=verification_passed,
        verification_detail=detail,
    )


def _solve_percent(problem: ParsedAlgebraProblem, rate: Fraction, value: Fraction) -> AlgebraSolveResponse:
    result = rate * value / 100
    verification_passed = result * 100 == rate * value
    return _response(
        problem,
        problem_type="percent",
        title="Tính phần trăm của một số",
        explanation="Đổi phần trăm thành phân số có mẫu 100 rồi nhân với giá trị.",
        rule="p% của a = p/100 × a",
        before=f"{_fraction_text(rate)}% của {_fraction_text(value)}",
        result=_fraction_text(result),
        result_latex=_fraction_latex(result),
        verification_name="percent_identity",
        verification_passed=verification_passed,
        verification_detail="Nhân ngược kết quả với 100 khôi phục tích rate × value.",
    )


def _solve_percent_ratio(problem: ParsedAlgebraProblem, part: Fraction, whole: Fraction) -> AlgebraSolveResponse:
    if whole == 0:
        return _unsupported(problem, "Giá trị toàn phần phải khác 0 khi tính tỉ lệ phần trăm.")
    result = part * 100 / whole
    return _response(
        problem,
        problem_type="percent_ratio",
        title="Tính tỉ lệ phần trăm",
        explanation="Chia phần cần so sánh cho toàn phần rồi nhân 100%.",
        rule="Tỉ lệ phần trăm = phần/toàn phần × 100%",
        before=f"{_fraction_text(part)}/{_fraction_text(whole)} × 100%",
        result=f"{_fraction_text(result)}%",
        result_latex=f"{_fraction_latex(result)}\\%",
        verification_name="percent_ratio_identity",
        verification_passed=whole * result == part * 100,
        verification_detail="Nhân chéo tỉ lệ phần trăm khôi phục phần và toàn phần ban đầu.",
    )


def _solve_percent_base(problem: ParsedAlgebraProblem, rate: Fraction, part: Fraction) -> AlgebraSolveResponse:
    if rate == 0:
        return _unsupported(problem, "Tỉ lệ phần trăm phải khác 0 khi tìm giá trị gốc.")
    result = part * 100 / rate
    return _response(
        problem,
        problem_type="percent_base",
        title="Tìm giá trị gốc từ phần trăm",
        explanation="Chia giá trị đã biết cho tỉ lệ viết dưới dạng phân số.",
        rule="Giá trị gốc = phần đã biết × 100 / p",
        before=f"{_fraction_text(part)} × 100/{_fraction_text(rate)}",
        result=_fraction_text(result),
        result_latex=_fraction_latex(result),
        verification_name="percent_base_identity",
        verification_passed=rate * result == part * 100,
        verification_detail="Tính lại p% của giá trị gốc thu được đúng phần đã biết.",
    )


def _solve_ratio(problem: ParsedAlgebraProblem, left: int, right: int) -> AlgebraSolveResponse:
    if right == 0:
        return _unsupported(problem, "Số hạng phải của tỉ lệ không được bằng 0.")
    divisor = math.gcd(abs(left), abs(right)) or 1
    normalized_left = left // divisor
    normalized_right = right // divisor
    if normalized_right < 0:
        normalized_left, normalized_right = -normalized_left, -normalized_right
    result = f"{normalized_left}:{normalized_right}"
    verification_passed = left * normalized_right == right * normalized_left
    return _response(
        problem,
        problem_type="ratio",
        title="Rút gọn tỉ lệ",
        explanation=f"Chia hai số hạng cho UCLN là {divisor}.",
        rule="Chia hai vế tỉ lệ cho cùng một số khác 0",
        before=f"{left}:{right}",
        result=result,
        result_latex=f"{normalized_left}:{normalized_right}",
        verification_name="ratio_cross_product",
        verification_passed=verification_passed,
        verification_detail="Tích chéo của tỉ lệ ban đầu và tỉ lệ rút gọn bằng nhau.",
    )


def _solve_word_inventory(
    problem: ParsedAlgebraProblem,
    start: Fraction,
    unit: str,
    operations: list[tuple[str, Fraction]],
) -> AlgebraSolveResponse:
    if start < 0 or any(value < 0 for _, value in operations):
        return _unsupported(problem, "Số lượng trong bài toán lời văn phải không âm.")
    current = start
    steps: list[AlgebraSolveStep] = []
    for index, (operation, value) in enumerate(operations, start=1):
        before = current
        current = current + value if operation == "add" else current - value
        if current < 0:
            return _unsupported(problem, "Dữ kiện làm số lượng còn lại âm; bài toán không hợp lệ.")
        symbol = "+" if operation == "add" else "-"
        result = f"{_fraction_text(current)} {_unit_text(unit)}"
        steps.append(AlgebraSolveStep(
            index=index,
            title="Cộng thêm số lượng" if operation == "add" else "Bớt số lượng",
            explanation="Giữ nguyên đơn vị và thực hiện phép tính theo diễn biến đề bài.",
            rule="Cộng số được thêm" if operation == "add" else "Trừ số đã bớt",
            before_latex=f"{_fraction_latex(before)} {symbol} {_fraction_latex(value)}",
            after_latex=f"{_fraction_latex(current)}\\,\\text{{{_unit_text(unit)}}}",
            result=result,
            result_latex=f"{_fraction_latex(current)}\\,\\text{{{_unit_text(unit)}}}",
            kind="solve",
            confidence="verified",
        ))
    recomputed = start + sum((value if operation == "add" else -value for operation, value in operations), Fraction(0))
    result_text = f"{_fraction_text(current)} {_unit_text(unit)}"
    result_latex = f"{_fraction_latex(current)}\\,\\text{{{_unit_text(unit)}}}"
    steps.append(conclusion_step(len(steps) + 1, f"Kết quả: {result_text}", result_latex))
    return AlgebraSolveResponse(
        input=problem.raw_input,
        normalized_input=problem.normalized_input,
        topic="arithmetic",
        problem_type="word_problem",
        status="solved" if recomputed == current else "error",
        answer=f"Kết quả: {result_text}",
        answer_latex=result_latex,
        solution_set=AlgebraSolutionSet(kind="expression", text=result_text, latex=result_latex),
        steps=steps,
        verification=AlgebraVerificationReport(
            status="verified" if recomputed == current else "failed",
            checks=[AlgebraVerificationCheck(
                name="word_problem_recompute",
                status="pass" if recomputed == current else "fail",
                detail="Tính lại độc lập toàn bộ chuỗi cộng/trừ và giữ nguyên đơn vị.",
                latex=result_latex,
            )],
            method=["word_problem_recompute", "unit_consistency"],
        ),
    )


def _solve_word_product(problem: ParsedAlgebraProblem, groups: Fraction, size: Fraction, unit: str) -> AlgebraSolveResponse:
    if groups < 0 or size < 0:
        return _unsupported(problem, "Số nhóm và số lượng mỗi nhóm phải không âm.")
    result = groups * size
    unit_text = _unit_text(unit)
    return _response(
        problem,
        problem_type="word_problem",
        title="Tính tổng số lượng theo nhóm",
        explanation="Nhân số nhóm với số lượng trong mỗi nhóm.",
        rule="Tổng số lượng = số nhóm × số lượng mỗi nhóm",
        before=f"{_fraction_text(groups)} × {_fraction_text(size)}",
        result=f"{_fraction_text(result)} {unit_text}",
        result_latex=f"{_fraction_latex(result)}\\,\\text{{{unit_text}}}",
        verification_name="word_product_recompute",
        verification_passed=(size == 0 or result / size == groups),
        verification_detail="Chia kết quả cho số lượng mỗi nhóm khôi phục số nhóm.",
    )


def _solve_word_share(problem: ParsedAlgebraProblem, total: Fraction, groups: Fraction, unit: str) -> AlgebraSolveResponse:
    if total < 0 or groups <= 0:
        return _unsupported(problem, "Tổng số lượng phải không âm và số nhóm phải dương.")
    result = total / groups
    unit_text = _unit_text(unit)
    return _response(
        problem,
        problem_type="word_problem",
        title="Chia đều số lượng",
        explanation="Chia tổng số lượng cho số nhóm nhận bằng nhau.",
        rule="Mỗi nhóm nhận = tổng số lượng / số nhóm",
        before=f"{_fraction_text(total)} / {_fraction_text(groups)}",
        result=f"{_fraction_text(result)} {unit_text}",
        result_latex=f"{_fraction_latex(result)}\\,\\text{{{unit_text}}}",
        verification_name="word_share_recompute",
        verification_passed=(result * groups == total),
        verification_detail="Nhân phần mỗi nhóm với số nhóm khôi phục tổng ban đầu.",
    )


def _unit_text(unit: str) -> str:
    return unit.replace("_", " ")


def _response(
    problem: ParsedAlgebraProblem,
    *,
    problem_type: str,
    title: str,
    explanation: str,
    rule: str,
    before: str,
    result: str,
    result_latex: str,
    verification_name: str,
    verification_passed: bool,
    verification_detail: str,
) -> AlgebraSolveResponse:
    answer = f"Kết quả: {result}"
    steps = [
        AlgebraSolveStep(
            index=1,
            title=title,
            explanation=explanation,
            rule=rule,
            before_latex=before,
            after_latex=result_latex,
            result=result,
            result_latex=result_latex,
            kind="solve",
            confidence="verified" if verification_passed else "unverified",
        ),
        conclusion_step(2, answer, result_latex),
    ]
    verification = AlgebraVerificationReport(
        status="verified" if verification_passed else "failed",
        checks=[AlgebraVerificationCheck(
            name=verification_name,
            status="pass" if verification_passed else "fail",
            detail=verification_detail,
            latex=result_latex,
        )],
        method=[verification_name],
    )
    return AlgebraSolveResponse(
        input=problem.raw_input,
        normalized_input=problem.normalized_input,
        topic="arithmetic",
        problem_type=problem_type,
        status="solved" if verification_passed else "error",
        answer=answer,
        answer_latex=result_latex,
        solution_set=AlgebraSolutionSet(kind="expression", text=result, latex=result_latex),
        steps=steps,
        verification=verification,
    )


def _fraction_text(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def _fraction_latex(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"\\frac{{{value.numerator}}}{{{value.denominator}}}"


def _unsupported(problem: ParsedAlgebraProblem, reason: str) -> AlgebraSolveResponse:
    return AlgebraSolveResponse(
        input=problem.raw_input,
        normalized_input=problem.normalized_input,
        topic="arithmetic",
        problem_type="unsupported",
        status="unsupported",
        answer=reason,
        warnings=[reason],
    )