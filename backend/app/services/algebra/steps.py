from __future__ import annotations

import sympy as sp

from app.schemas.algebra import AlgebraSolveStep
from app.services.algebra.parser import ParsedAlgebraProblem


def normalize_step(problem: ParsedAlgebraProblem) -> AlgebraSolveStep:
    return AlgebraSolveStep(
        index=1,
        title="Chuẩn hóa đề bài",
        explanation="Hệ thống chuyển biểu thức về dạng SymPy an toàn để xử lý symbolic.",
        expression=problem.normalized_input,
        expression_latex=sp.latex(problem.relation) if problem.relation is not None else sp.latex(problem.expression),
        kind="normalize",
        confidence="symbolic",
    )


def domain_step(index: int, assumptions: list[str]) -> AlgebraSolveStep:
    return AlgebraSolveStep(
        index=index,
        title="Điều kiện xác định",
        explanation="; ".join(assumptions) if assumptions else "Chưa phát hiện điều kiện loại trừ đặc biệt trong phạm vi solver hiện tại.",
        kind="domain",
        confidence="symbolic",
    )


def conclusion_step(index: int, answer: str, answer_latex: str | None) -> AlgebraSolveStep:
    return AlgebraSolveStep(
        index=index,
        title="Kết luận",
        explanation=answer,
        result=answer,
        result_latex=answer_latex,
        kind="conclusion",
        confidence="verified",
    )
