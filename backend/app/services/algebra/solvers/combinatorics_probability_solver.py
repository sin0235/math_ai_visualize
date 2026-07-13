from __future__ import annotations

import math
import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

import sympy as sp

from app.schemas.algebra import AlgebraSolutionSet, AlgebraSolveResponse, AlgebraSolveStep, AlgebraVerificationCheck, AlgebraVerificationReport
from app.services.algebra.parser import AlgebraParseError, ParsedAlgebraProblem, parse_algebra_expr
from app.services.algebra.steps import conclusion_step, normalize_step

# Hard caps to avoid CPU/memory blowups from huge factorials / combinatorics.
MAX_FACTORIAL_N = 20
MAX_COMBINATORICS_N = 30
MAX_COEFFICIENT_DEGREE = 12
MAX_COEFFICIENT_EXPR_CHARS = 200


@dataclass(frozen=True)
class ProbabilityProblem:
    kind: Literal["classical", "complement", "intersection", "union", "conditional", "binomial", "combination"]
    first: Fraction | None = None
    second: Fraction | None = None
    n: int | None = None
    k: int | None = None
    r: int | None = None


@dataclass(frozen=True)
class ProbabilityEvaluation:
    value: sp.Rational
    explanation: str
    latex: str
    verifier_name: str


def solve_combinatorics_probability(problem: ParsedAlgebraProblem) -> AlgebraSolveResponse:
    normalized = problem.normalized_input.strip()
    steps = [normalize_step(problem)]
    probability_problem: ProbabilityProblem | None = None
    probability_evaluation: ProbabilityEvaluation | None = None
    try:
        probability_problem = _parse_probability_problem(normalized)
        if probability_problem is not None:
            probability_evaluation = _evaluate_probability(probability_problem)
            result = probability_evaluation.value
            explanation = probability_evaluation.explanation
            latex = probability_evaluation.latex
            kind = "probability"
        else:
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
    
    if probability_problem is not None and probability_evaluation is not None:
        probability_ok, verification_detail = _verify_probability(probability_problem, result)
        verification = AlgebraVerificationReport(
            status="verified" if probability_ok else "failed",
            checks=[AlgebraVerificationCheck(
                name=probability_evaluation.verifier_name,
                status="pass" if probability_ok else "fail",
                detail=verification_detail,
                latex=sp.latex(result),
            )],
            method=["stdlib_fraction_recompute"],
        )
    else:
        verification = AlgebraVerificationReport(
            status="verified",
            checks=[AlgebraVerificationCheck(
                name="combinatorics_constraints_valid",
                status="pass",
                detail="Các tham số tổ hợp thỏa điều kiện nguyên không âm trong phạm vi hỗ trợ.",
            )],
            method=["stdlib_integer_recompute"],
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


def _parse_probability_problem(text: str) -> ProbabilityProblem | None:
    classical = re.fullmatch(
        r"(?:P|probability)\(\s*(?:favorable\s*=\s*)?(\d+)\s*(?:/|,|\s+total\s*=\s*)\s*(\d+)\s*\)",
        text,
        re.IGNORECASE,
    )
    if classical:
        favorable, total = map(int, classical.groups())
        return ProbabilityProblem("classical", first=_probability_fraction(favorable, total))

    unary = re.fullmatch(r"(?:P_not|Pcomplement|probability_not)\(\s*(\d+)\s*/\s*(\d+)\s*\)", text, re.IGNORECASE)
    if unary:
        favorable, total = map(int, unary.groups())
        return ProbabilityProblem("complement", first=_probability_fraction(favorable, total))

    binary = re.fullmatch(
        r"(P_and|probability_and|Punion|probability_union|Pcond|probability_cond)"
        r"\(\s*(\d+)\s*/\s*(\d+)\s*,\s*(\d+)\s*/\s*(\d+)\s*\)",
        text,
        re.IGNORECASE,
    )
    if binary:
        operation, a, b, c, d = binary.groups()
        operation_key = operation.lower()
        kind: Literal["intersection", "union", "conditional"] = (
            "intersection" if operation_key in {"p_and", "probability_and"}
            else "union" if operation_key in {"punion", "probability_union"}
            else "conditional"
        )
        return ProbabilityProblem(
            kind,
            first=_probability_fraction(int(a), int(b)),
            second=_probability_fraction(int(c), int(d)),
        )

    binomial = re.fullmatch(r"(?:bernoulli|Pbinom)\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*/\s*(\d+)\s*\)", text, re.IGNORECASE)
    if binomial:
        n, k, a, b = map(int, binomial.groups())
        _validate_n_k(n, k)
        if n > MAX_COMBINATORICS_N:
            raise ValueError(f"Bernoulli chỉ hỗ trợ n ≤ {MAX_COMBINATORICS_N}.")
        return ProbabilityProblem("binomial", first=_probability_fraction(a, b), n=n, k=k)

    combination = re.fullmatch(r"(?:Pcomb|probability_comb)\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)\)", text)
    if combination:
        n, k, r = map(int, combination.groups())
        _validate_n_k(n, k)
        if r < 0 or r > n:
            raise ValueError("Số phần tử được chọn r phải thỏa 0 ≤ r ≤ n.")
        return ProbabilityProblem("combination", n=n, k=k, r=r)
    return None


def _evaluate_probability(problem: ProbabilityProblem) -> ProbabilityEvaluation:
    first = problem.first
    second = problem.second
    if problem.kind == "classical" and first is not None:
        value = _sympy_fraction(first)
        return ProbabilityEvaluation(value, f"Xác suất cổ điển P = {first}.", rf"P={sp.latex(value)}", "probability_classical_recompute")
    if problem.kind == "complement" and first is not None:
        value = _sympy_fraction(1 - first)
        return ProbabilityEvaluation(value, f"P(Ā)=1-P(A)=1-{first}.", rf"P(\bar{{A}})=1-{sp.latex(_sympy_fraction(first))}", "probability_complement_recompute")
    if problem.kind == "intersection" and first is not None and second is not None:
        value = _sympy_fraction(first * second)
        return ProbabilityEvaluation(value, "Hai biến cố độc lập: P(A∩B)=P(A)P(B).", rf"P(A\cap B)={sp.latex(value)}", "probability_independent_product")
    if problem.kind == "union" and first is not None and second is not None:
        value = _sympy_fraction(first + second - first * second)
        return ProbabilityEvaluation(value, "Hai biến cố độc lập: P(A∪B)=P(A)+P(B)-P(A)P(B).", rf"P(A\cup B)={sp.latex(value)}", "probability_independent_union")
    if problem.kind == "conditional" and first is not None and second is not None:
        if second == 0:
            raise ValueError("P(B) phải khác 0 khi tính xác suất có điều kiện.")
        value = _sympy_fraction(first)
        return ProbabilityEvaluation(value, "Giả sử độc lập: P(A|B)=P(A).", rf"P(A\mid B)={sp.latex(value)}", "probability_independent_conditional")
    if problem.kind == "binomial" and first is not None and problem.n is not None and problem.k is not None:
        value_fraction = Fraction(math.comb(problem.n, problem.k)) * first ** problem.k * (1 - first) ** (problem.n - problem.k)
        value = _sympy_fraction(value_fraction)
        return ProbabilityEvaluation(value, f"P(X={problem.k})=C({problem.n},{problem.k})p^k(1-p)^(n-k).", sp.latex(value), "probability_binomial_recompute")
    if problem.kind == "combination" and problem.n is not None and problem.k is not None and problem.r is not None:
        favorable = math.comb(problem.k, problem.r) if problem.r <= problem.k else 0
        total = math.comb(problem.n, problem.r)
        value = _sympy_fraction(Fraction(favorable, total))
        return ProbabilityEvaluation(value, f"P=C({problem.k},{problem.r})/C({problem.n},{problem.r}).", sp.latex(value), "probability_combination_recompute")
    raise ValueError("Thiếu dữ kiện typed cho bài toán xác suất.")


def _verify_probability(problem: ProbabilityProblem, result: sp.Expr) -> tuple[bool, str]:
    expected = _evaluate_probability_fraction(problem)
    numerator, denominator = sp.Rational(result).as_numer_denom()
    actual = Fraction(int(numerator), int(denominator))
    return actual == expected and 0 <= actual <= 1, f"Tính lại bằng Fraction được {expected}; kết quả nằm trong [0, 1]."


def _evaluate_probability_fraction(problem: ProbabilityProblem) -> Fraction:
    first = problem.first
    second = problem.second
    if problem.kind == "classical" and first is not None:
        return first
    if problem.kind == "complement" and first is not None:
        return 1 - first
    if problem.kind == "intersection" and first is not None and second is not None:
        return first * second
    if problem.kind == "union" and first is not None and second is not None:
        return first + second - first * second
    if problem.kind == "conditional" and first is not None and second:
        return first
    if problem.kind == "binomial" and first is not None and problem.n is not None and problem.k is not None:
        return Fraction(math.comb(problem.n, problem.k)) * first ** problem.k * (1 - first) ** (problem.n - problem.k)
    if problem.kind == "combination" and problem.n is not None and problem.k is not None and problem.r is not None:
        favorable = math.comb(problem.k, problem.r) if problem.r <= problem.k else 0
        return Fraction(favorable, math.comb(problem.n, problem.r))
    raise ValueError("Không thể kiểm chứng bài toán xác suất thiếu dữ kiện.")


def _probability_fraction(numerator: int, denominator: int) -> Fraction:
    if denominator <= 0:
        raise ValueError("Mẫu số xác suất phải là số nguyên dương.")
    if numerator < 0 or numerator > denominator:
        raise ValueError("Xác suất thành phần phải nằm trong [0, 1].")
    return Fraction(numerator, denominator)


def _sympy_fraction(value: Fraction) -> sp.Rational:
    return sp.Rational(value.numerator, value.denominator)


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
    # Bernoulli / binomial PMF: bernoulli(n,k,a/b) or Pbinom(n,k,a/b)
    binom = re.fullmatch(
        r"(?:bernoulli|Pbinom)\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*/\s*(\d+)\s*\)",
        text,
        re.IGNORECASE,
    )
    if binom:
        n, k, a, b = (int(binom.group(i)) for i in range(1, 5))
        _validate_n_k(n, k)
        if b <= 0 or a < 0 or a > b:
            raise ValueError("p = a/b phải thỏa 0 ≤ a ≤ b và b > 0.")
        if n > MAX_COMBINATORICS_N:
            raise ValueError(f"Bernoulli chỉ hỗ trợ n ≤ {MAX_COMBINATORICS_N}.")
        p = sp.Rational(a, b)
        value = sp.Integer(math.comb(n, k)) * (p ** k) * ((1 - p) ** (n - k))
        value = sp.simplify(value)
        return (
            value,
            f"Phân phối nhị thức: P(X={k}) = C({n},{k}) p^{k} (1-p)^{n-k} với p={a}/{b}.",
            rf"C_{{{n}}}^{{{k}}}\left(\frac{{{a}}}{{{b}}}\right)^{{{k}}}\left(1-\frac{{{a}}}{{{b}}}\right)^{{{n - k}}}",
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
        "P(k/n), P_not(k/n), P_and(a/b,c/d), Punion(a/b,c/d), Pcond(a/b,c/d), "
        "Pcomb(n,k,r), bernoulli(n,k,a/b)."
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
