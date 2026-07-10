from __future__ import annotations

import math
import re

import sympy as sp

from app.schemas.algebra import AlgebraSolutionSet, AlgebraSolveResponse, AlgebraSolveStep, AlgebraVerificationCheck, AlgebraVerificationReport
from app.services.algebra.parser import AlgebraParseError, ParsedAlgebraProblem, parse_algebra_expr
from app.services.algebra.steps import conclusion_step, normalize_step

# Hard caps to avoid CPU/memory blowups from huge factorials / combinatorics.
MAX_FACTORIAL_N = 20
MAX_COMBINATORICS_N = 30
MAX_COEFFICIENT_DEGREE = 12
MAX_COEFFICIENT_EXPR_CHARS = 200


def solve_combinatorics_probability(problem: ParsedAlgebraProblem) -> AlgebraSolveResponse:
    normalized = problem.normalized_input.strip()
    steps = [normalize_step(problem)]
    try:
        result, explanation, latex, kind = _evaluate(normalized)
    except ValueError as exc:
        return _unsupported(problem, str(exc))
    title = "Tính xác suất" if kind == "probability" else "Tính toán tổ hợp"
    steps.append(AlgebraSolveStep(
        index=2,
        title=title,
        explanation=explanation,
        expression=normalized,
        expression_latex=latex,
        result=sp.sstr(result),
        result_latex=sp.latex(result),
        kind="solve",
        confidence="symbolic",
    ))
    answer = f"Kết quả: {sp.sstr(result)}"
    steps.append(conclusion_step(3, answer, sp.latex(result)))
    
    milestones = [
        f"Biểu thức gốc: {latex}",
        f"Kết quả: {sp.latex(result)}"
    ]
    
    verification = AlgebraVerificationReport(
        status="verified" if kind != "probability" else "partially_verified",
        checks=[
            AlgebraVerificationCheck(
                name="combinatorics_constraints_valid" if kind != "probability" else "probability_bounds_valid",
                status="pass",
                detail=(
                    "Các tham số tổ hợp thỏa điều kiện nguyên không âm trong phạm vi hỗ trợ."
                    if kind != "probability"
                    else "Xác suất cổ điển 0 ≤ k/n ≤ 1 với n > 0 (rule-based)."
                ),
            )
        ],
        method=["rule_based"],
    )
    return AlgebraSolveResponse(
        input=problem.raw_input,
        normalized_input=problem.normalized_input,
        topic="combinatorics_probability",
        problem_type="calculate_probability" if kind == "probability" else "calculate_combinatorics",
        status="solved",
        answer=answer,
        answer_latex=sp.latex(result),
        solution_set=AlgebraSolutionSet(kind="expression", text=sp.sstr(result), latex=sp.latex(result)),
        steps=steps,
        milestones=milestones,
        verification=verification,
        assumptions=[],
        warnings=[],
        errors=[],
    )


def _evaluate(text: str) -> tuple[sp.Expr, str, str, str]:
    """Return (result, explanation, latex, kind) where kind is combinatorics|probability."""
    # Classical probability: P(k/n), P(favorable=k,total=n), probability(k,n)
    probability = re.fullmatch(
        r"(?:P|probability)\(\s*(?:favorable\s*=\s*)?(\d+)\s*(?:/|,|\s+total\s*=\s*)\s*(\d+)\s*\)",
        text,
        re.IGNORECASE,
    )
    if probability:
        k, n = int(probability.group(1)), int(probability.group(2))
        if n <= 0:
            raise ValueError("Mẫu số (tổng số kết quả) phải là số nguyên dương.")
        if k < 0 or k > n:
            raise ValueError("Số kết quả thuận lợi k phải thỏa 0 ≤ k ≤ n.")
        value = sp.Rational(k, n)
        return (
            value,
            f"Xác suất cổ điển P = k/n = {k}/{n}.",
            rf"P=\frac{{{k}}}{{{n}}}",
            "probability",
        )
    # Complement: P_not(k/n) = 1 - k/n
    complement = re.fullmatch(
        r"(?:P_not|Pcomplement|probability_not)\(\s*(\d+)\s*/\s*(\d+)\s*\)",
        text,
        re.IGNORECASE,
    )
    if complement:
        k, n = int(complement.group(1)), int(complement.group(2))
        if n <= 0:
            raise ValueError("Mẫu số (tổng số kết quả) phải là số nguyên dương.")
        if k < 0 or k > n:
            raise ValueError("Số kết quả thuận lợi k phải thỏa 0 ≤ k ≤ n.")
        value = sp.Rational(n - k, n)
        return (
            value,
            f"Xác suất phần bù P(Ā) = 1 − P(A) = 1 − {k}/{n} = {n - k}/{n}.",
            rf"P(\bar{{A}})=1-\frac{{{k}}}{{{n}}}=\frac{{{n - k}}}{{{n}}}",
            "probability",
        )
    # Independent product: P_and(p,q) with p,q as fractions a/b,c/d
    independent = re.fullmatch(
        r"(?:P_and|probability_and)\(\s*(\d+)\s*/\s*(\d+)\s*,\s*(\d+)\s*/\s*(\d+)\s*\)",
        text,
        re.IGNORECASE,
    )
    if independent:
        a, b, c, d = (int(independent.group(i)) for i in range(1, 5))
        pa, pb = _validate_probability_pair(a, b, c, d)
        value = pa * pb
        return (
            value,
            f"Hai biến cố độc lập: P(A∩B) = P(A)·P(B) = ({a}/{b})·({c}/{d}).",
            rf"P(A\cap B)=\frac{{{a}}}{{{b}}}\cdot\frac{{{c}}}{{{d}}}",
            "probability",
        )
    # Independent union: Punion(a/b,c/d) = P(A)+P(B)-P(A)P(B)
    punion = re.fullmatch(
        r"(?:Punion|probability_union)\(\s*(\d+)\s*/\s*(\d+)\s*,\s*(\d+)\s*/\s*(\d+)\s*\)",
        text,
        re.IGNORECASE,
    )
    if punion:
        a, b, c, d = (int(punion.group(i)) for i in range(1, 5))
        pa, pb = _validate_probability_pair(a, b, c, d)
        value = pa + pb - pa * pb
        return (
            value,
            f"Hai biến cố độc lập: P(A∪B) = P(A)+P(B)−P(A)P(B) = {a}/{b} + {c}/{d} − ({a}/{b})({c}/{d}).",
            rf"P(A\cup B)=\frac{{{a}}}{{{b}}}+\frac{{{c}}}{{{d}}}-\frac{{{a}}}{{{b}}}\cdot\frac{{{c}}}{{{d}}}",
            "probability",
        )
    # Conditional under independence: Pcond(a/b,c/d) = P(A∩B)/P(B) = P(A)
    # (documented assumption: A,B independent → P(A|B)=P(A))
    pcond = re.fullmatch(
        r"(?:Pcond|probability_cond)\(\s*(\d+)\s*/\s*(\d+)\s*,\s*(\d+)\s*/\s*(\d+)\s*\)",
        text,
        re.IGNORECASE,
    )
    if pcond:
        a, b, c, d = (int(pcond.group(i)) for i in range(1, 5))
        pa, pb = _validate_probability_pair(a, b, c, d)
        if pb == 0:
            raise ValueError("P(B) phải khác 0 khi tính xác suất có điều kiện.")
        value = pa  # independence assumption
        return (
            value,
            f"Giả sử A,B độc lập: P(A|B) = P(A∩B)/P(B) = P(A)·P(B)/P(B) = P(A) = {a}/{b}.",
            rf"P(A\mid B)=\frac{{{a}}}{{{b}}}\ \text{{(độc lập)}}",
            "probability",
        )
    # Combination probability: P(C(n,k)/C(n,m)) style — Pcomb(n,k,total_choose)
    pcomb = re.fullmatch(r"(?:Pcomb|probability_comb)\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)\)", text)
    if pcomb:
        n, k, r = int(pcomb.group(1)), int(pcomb.group(2)), int(pcomb.group(3))
        _validate_n_k(n, k)
        if r < 0 or r > n:
            raise ValueError("Số phần tử được chọn r phải thỏa 0 ≤ r ≤ n.")
        if k > r:
            raise ValueError("Không thể có k thuận lợi lớn hơn r phần tử được chọn.")
        total = math.comb(n, r)
        fav = math.comb(k, r) if r <= k else 0
        # Actually typical: choose r from n, favorable if all from k marked — C(k,r)/C(n,r) when r<=k
        fav = math.comb(k, r) if r <= k else 0
        if total == 0:
            raise ValueError("Không xác định được mẫu số tổ hợp.")
        value = sp.Rational(fav, total)
        return (
            value,
            f"Xác suất chọn {r} phần tử từ n={n} với {k} phần tử đánh dấu: C({k},{r})/C({n},{r}).",
            rf"P=\frac{{C_{{{k}}}^{{{r}}}}}{{C_{{{n}}}^{{{r}}}}}",
            "probability",
        )
    permutation = re.fullmatch(r"A\((\d+)\s*,\s*(\d+)\)", text)
    if permutation:
        n, k = _parse_pair(permutation)
        _validate_n_k(n, k)
        return sp.Integer(math.perm(n, k)), f"Tính chỉnh hợp A({n}, {k}) = n!/(n-k)!.", f"A_{{{n}}}^{{{k}}}", "combinatorics"
    combination = re.fullmatch(r"(?:C|binomial)\((\d+)\s*,\s*(\d+)\)", text)
    if combination:
        n, k = _parse_pair(combination)
        _validate_n_k(n, k)
        return sp.Integer(math.comb(n, k)), f"Tính tổ hợp C({n}, {k}) = n!/(k!(n-k)!).", f"C_{{{n}}}^{{{k}}}", "combinatorics"
    factorial = re.fullmatch(r"(?:factorial\((\d+)\)|(\d+)!)", text)
    if factorial:
        n = int(factorial.group(1) or factorial.group(2))
        if n < 0:
            raise ValueError("Giai thừa chỉ hỗ trợ số nguyên không âm.")
        if n > MAX_FACTORIAL_N:
            raise ValueError(f"Giai thừa chỉ hỗ trợ n ≤ {MAX_FACTORIAL_N} (nhận được n={n}).")
        return sp.Integer(math.factorial(n)), f"Tính giai thừa {n}!.", f"{n}!", "combinatorics"
    coefficient = re.fullmatch(r"coefficient\((.+),\s*([A-Za-z])\s*,\s*(-?\d+)\)", text)
    if coefficient:
        expr_text, variable_name, power_text = coefficient.groups()
        if len(expr_text) > MAX_COEFFICIENT_EXPR_CHARS:
            raise ValueError(f"Biểu thức hệ số vượt quá {MAX_COEFFICIENT_EXPR_CHARS} ký tự.")
        try:
            expression = parse_algebra_expr(expr_text, variable_names=[variable_name], real=True)
        except AlgebraParseError as exc:
            raise ValueError(f"Không đọc được biểu thức hệ số: {exc}") from exc
        power = int(power_text)
        if abs(power) > MAX_COEFFICIENT_DEGREE:
            raise ValueError(f"Bậc hệ số chỉ hỗ trợ |k| ≤ {MAX_COEFFICIENT_DEGREE}.")
        variable = sp.Symbol(variable_name, real=True)
        result = sp.expand(expression).coeff(variable, power)
        return result, f"Khai triển biểu thức và lấy hệ số của {variable_name}^{power}.", sp.latex(expression), "combinatorics"
    raise ValueError(
        "Dạng tổ hợp-xác suất chưa hỗ trợ. Dùng C(n,k), A(n,k), n!, coefficient(...), "
        "P(k/n), P_not(k/n), P_and(a/b,c/d), Punion(a/b,c/d), Pcond(a/b,c/d), Pcomb(n,k,r)."
    )


def _validate_probability_pair(a: int, b: int, c: int, d: int) -> tuple[sp.Rational, sp.Rational]:
    if b <= 0 or d <= 0:
        raise ValueError("Mẫu số xác suất phải là số nguyên dương.")
    if a < 0 or a > b or c < 0 or c > d:
        raise ValueError("Mỗi xác suất thành phần phải nằm trong [0, 1].")
    return sp.Rational(a, b), sp.Rational(c, d)


def _parse_pair(match: re.Match[str]) -> tuple[int, int]:
    return int(match.group(1)), int(match.group(2))


def _validate_n_k(n: int, k: int) -> None:
    if n < 0 or k < 0:
        raise ValueError("n và k phải là số nguyên không âm.")
    if k > n:
        raise ValueError("Cần có k <= n trong tổ hợp/chỉnh hợp.")
    if n > MAX_COMBINATORICS_N:
        raise ValueError(f"Tổ hợp/chỉnh hợp chỉ hỗ trợ n ≤ {MAX_COMBINATORICS_N} (nhận được n={n}).")


def _unsupported(problem: ParsedAlgebraProblem, message: str) -> AlgebraSolveResponse:
    return AlgebraSolveResponse(input=problem.raw_input, normalized_input=problem.normalized_input, topic="combinatorics_probability", problem_type="calculate_combinatorics", status="unsupported", answer=message, errors=[message])
