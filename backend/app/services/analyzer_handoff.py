from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from app.schemas.analyzer_links import (
    AlgebraHandoffPayload,
    AnalyzerHandoffPayload,
    AnalyzerTarget,
    GeoGebraHandoffPayload,
    PracticeHandoffPayload,
    RenderHandoffPayload,
    SimulationHandoffPayload,
)


def build_analyzer_handoff_payload(target: AnalyzerTarget, result: dict[str, Any]) -> AnalyzerHandoffPayload:
    expression = str(result.get("evaluated_expression") or result.get("expression") or "").strip()
    verification = str((result.get("verification") or {}).get("status") or "unverified")
    if not expression:
        raise _unsupported("Kết quả analyzer không có biểu thức hợp lệ để chuyển tiếp.")

    if target == "algebra_solver":
        derivative = str(result.get("derivative") or "").strip()
        if not derivative:
            raise _unsupported("Kết quả chưa có đạo hàm để mở Algebra Solver.")
        return AlgebraHandoffPayload(input=f"({derivative}) = 0")

    if target == "simulation":
        window = (result.get("graph_analysis_v2") or {}).get("window") or {}
        x_min = _finite_bound(window.get("x_min"), -5.0)
        x_max = _finite_bound(window.get("x_max"), 5.0)
        if x_min >= x_max:
            x_min, x_max = -5.0, 5.0
        return SimulationHandoffPayload(
            expression=expression,
            x_min=x_min,
            x_max=x_max,
            verification_status=verification,
        )

    if target == "geogebra_lab":
        commands = [str(command).strip()[:500] for command in (result.get("geogebra_commands") or []) if str(command).strip()]
        if not commands:
            raise _unsupported("Kết quả chưa có lệnh GeoGebra do backend xác nhận.")
        return GeoGebraHandoffPayload(commands=commands[:40])

    if target == "render":
        return RenderHandoffPayload(problem_text=f"Vẽ đồ thị hàm số y = {expression}, thể hiện các đặc trưng đã xác định.")

    steps = [step for step in (result.get("analysis_steps") or []) if step.get("status") in {"complete", "partial"}]
    topics = ", ".join(str(step.get("title")) for step in steps[:5] if step.get("title")) or "tập xác định, đạo hàm và biến thiên"
    return PracticeHandoffPayload(
        problem_text=(
            f"Tạo bài luyện tập về hàm số f(x) = {expression}. "
            f"Yêu cầu học sinh tự xác định {topics}; không tiết lộ đáp án trong đề."
        ),
        source_verification=verification,
    )


def _finite_bound(value: Any, fallback: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return number if -1_000_000 <= number <= 1_000_000 else fallback


def _unsupported(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=message)