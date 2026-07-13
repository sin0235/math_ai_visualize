from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal

import sympy as sp

from app.services.geometry_facts import GeometryFact, build_geometry_fact_graph
from app.services.safe_math_parser import SafeMathComplexityError, SafeMathParseError, parse_safe_math_expression

PlaneMetricTask = Literal["area", "perimeter"]
PlaneShape = Literal["rectangle", "square", "parallelogram", "trapezoid", "circle"]
PlaneShapeStatus = Literal["ok", "missing_premise", "invalid"]


@dataclass(frozen=True)
class PlaneShapeGoal:
    shape: PlaneShape
    task: PlaneMetricTask


@dataclass(frozen=True)
class PlaneShapeResult:
    status: PlaneShapeStatus
    goal: PlaneShapeGoal | None = None
    value: sp.Expr | None = None
    result_latex: str | None = None
    formula_latex: str | None = None
    substitution_latex: str | None = None
    verifier_latex: str | None = None
    premise_facts: tuple[GeometryFact, ...] = ()
    missing_premises: tuple[str, ...] = ()
    warning: str | None = None


_FORMULAS: dict[tuple[PlaneShape, PlaneMetricTask], tuple[tuple[str, ...], str]] = {
    ("rectangle", "area"): (("length", "width"), "S=l\\cdot w"),
    ("rectangle", "perimeter"): (("length", "width"), "P=2(l+w)"),
    ("square", "area"): (("side",), "S=a^2"),
    ("square", "perimeter"): (("side",), "P=4a"),
    ("parallelogram", "area"): (("base", "height"), "S=a\\cdot h"),
    ("trapezoid", "area"): (("base1", "base2", "height"), "S=\\frac{(a+b)h}{2}"),
    ("circle", "area"): (("radius",), "S=\\pi r^2"),
    ("circle", "perimeter"): (("radius",), "C=2\\pi r"),
}


# ponytail: Chỉ giải metric trực tiếp từ scalar facts; proof phân loại tứ giác và định lý đường tròn để Stage 5 xử lý.
def solve_plane_shape_metric(scene: dict[str, Any], question: str) -> PlaneShapeResult:
    goal = parse_plane_shape_goal(question)
    if goal is None:
        return PlaneShapeResult(status="invalid", warning="Chưa nhận diện được hình hoặc đại lượng cần tính.")
    contract = _FORMULAS.get((goal.shape, goal.task))
    if contract is None:
        return PlaneShapeResult(
            status="invalid",
            goal=goal,
            warning="Dạng metric này chưa có công thức THCS được đăng ký.",
        )
    required, formula = contract
    values, facts, missing, error = _measure_values(scene, required)
    if error:
        return PlaneShapeResult(status="invalid", goal=goal, warning=error)
    if missing:
        return PlaneShapeResult(
            status="missing_premise",
            goal=goal,
            premise_facts=tuple(facts),
            missing_premises=tuple(missing),
            warning=f"Thiếu dữ kiện exact: {', '.join(missing)}.",
        )

    value = _evaluate(goal, values)
    if value is None or value.is_positive is not True:
        return PlaneShapeResult(status="invalid", goal=goal, warning="Dữ kiện metric không tạo được kết quả dương hợp lệ.")
    substitution = _substitution(goal, values)
    verifier = _verifier(goal, values, value)
    if not _verify_result(goal, values, value):
        return PlaneShapeResult(status="invalid", goal=goal, warning="Kết quả không vượt qua kiểm tra tính lại độc lập.")
    return PlaneShapeResult(
        status="ok",
        goal=goal,
        value=value,
        result_latex=sp.latex(value),
        formula_latex=formula,
        substitution_latex=substitution,
        verifier_latex=verifier,
        premise_facts=tuple(facts),
    )


def parse_plane_shape_goal(question: str) -> PlaneShapeGoal | None:
    plain = _plain(question)
    task: PlaneMetricTask | None = None
    if re.search(r"dien tich|\barea\b", plain):
        task = "area"
    elif re.search(r"chu vi|perimeter|circumference", plain):
        task = "perimeter"
    shape: PlaneShape | None = None
    for candidate, pattern in (
        ("rectangle", r"hinh chu nhat|rectangle"),
        ("square", r"hinh vuong|square"),
        ("parallelogram", r"hinh binh hanh|parallelogram"),
        ("trapezoid", r"hinh thang|trapezoid"),
        ("circle", r"hinh tron|duong tron|circle"),
    ):
        if re.search(pattern, plain):
            shape = candidate
            break
    return PlaneShapeGoal(shape=shape, task=task) if shape and task else None


def _measure_values(
    scene: dict[str, Any],
    required: tuple[str, ...],
) -> tuple[dict[str, sp.Expr], list[GeometryFact], list[str], str | None]:
    graph = build_geometry_fact_graph(scene)
    values: dict[str, sp.Expr] = {}
    facts: list[GeometryFact] = []
    for fact in graph.by_type("scalar_measure"):
        name = str(fact.args.get("name") or "")
        if name not in required:
            continue
        value = _positive_exact(fact.args.get("label"))
        if value is None:
            return {}, [], [], f"Dữ kiện {name} phải là số exact dương."
        if name in values and sp.simplify(values[name] - value) != 0:
            return {}, [], [], f"Dữ kiện {name} bị mâu thuẫn."
        if name not in values:
            values[name] = value
            facts.append(fact)
    missing = [name for name in required if name not in values]
    return values, facts, missing, None


def _evaluate(goal: PlaneShapeGoal, values: dict[str, sp.Expr]) -> sp.Expr | None:
    if goal.shape == "rectangle":
        return values["length"] * values["width"] if goal.task == "area" else 2 * (values["length"] + values["width"])
    if goal.shape == "square":
        return values["side"] ** 2 if goal.task == "area" else 4 * values["side"]
    if goal.shape == "parallelogram" and goal.task == "area":
        return values["base"] * values["height"]
    if goal.shape == "trapezoid" and goal.task == "area":
        return (values["base1"] + values["base2"]) * values["height"] / 2
    if goal.shape == "circle":
        return sp.pi * values["radius"] ** 2 if goal.task == "area" else 2 * sp.pi * values["radius"]
    return None


def _substitution(goal: PlaneShapeGoal, values: dict[str, sp.Expr]) -> str:
    args = ",".join(f"{name}={sp.latex(value)}" for name, value in values.items())
    return f"{goal.shape}({args})"


def _verifier(goal: PlaneShapeGoal, values: dict[str, sp.Expr], value: sp.Expr) -> str:
    return f"{sp.latex(value)}={sp.latex(sp.simplify(_evaluate(goal, values)))}"


def _verify_result(goal: PlaneShapeGoal, values: dict[str, sp.Expr], result: sp.Expr) -> bool:
    if goal.shape == "rectangle":
        expected = values["length"] * values["width"] if goal.task == "area" else 2 * values["length"] + 2 * values["width"]
    elif goal.shape == "square":
        expected = values["side"] * values["side"] if goal.task == "area" else values["side"] * 4
    elif goal.shape == "parallelogram" and goal.task == "area":
        expected = values["height"] * values["base"]
    elif goal.shape == "trapezoid" and goal.task == "area":
        expected = values["height"] * (values["base2"] + values["base1"]) / 2
    elif goal.shape == "circle":
        expected = values["radius"] ** 2 * sp.pi if goal.task == "area" else values["radius"] * 2 * sp.pi
    else:
        return False
    return sp.simplify(result - expected) == 0


def _positive_exact(value: Any) -> sp.Expr | None:
    text = str(value or "").strip().replace(",", ".").replace("√", "sqrt")
    text = re.sub(r"sqrt\s*([0-9]+(?:\.[0-9]+)?)", r"sqrt(\1)", text)
    try:
        exact = sp.simplify(parse_safe_math_expression(text).expr)
    except (SafeMathComplexityError, SafeMathParseError, TypeError, ValueError):
        return None
    return exact if not exact.free_symbols and exact.is_real is True and exact.is_positive is True else None


def _plain(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.lower())
    text = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", text.replace("đ", "d")).strip()