from __future__ import annotations

from typing import Any, Mapping


_STEP_DEFINITIONS = (
    ("domain", "Tập xác định", "domain_latex", "domain"),
    ("limits", "Giới hạn và tiệm cận", None, "asymptotes"),
    ("derivative", "Đạo hàm cấp một", "derivative_latex", "derivative"),
    ("critical_points", "Điểm tới hạn", None, "critical_points"),
    ("monotonicity", "Khoảng đơn điệu", None, "monotonicity"),
    ("extrema", "Cực trị", None, "critical_points"),
    ("second_derivative", "Đạo hàm cấp hai", "second_derivative_latex", "second_derivative"),
    ("concavity", "Khoảng lồi lõm", None, "concavity"),
    ("inflection_points", "Điểm uốn", None, "inflection_points"),
    ("intercepts", "Giao điểm với các trục", None, "roots"),
    ("variation_table", "Bảng biến thiên và kết luận", None, "variation_table"),
)


def build_analysis_steps(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Dựng trình tự trình bày từ evidence đã có; không chạy phép toán mới."""
    return [
        {
            "key": key,
            "order": order,
            "title": title,
            "status": _step_status(result, key, stage),
            "formula_latex": result.get(formula_key) if formula_key else None,
            "evidence": _step_evidence(result, key),
            "warnings": _step_warnings(result, key, stage),
        }
        for order, (key, title, formula_key, stage) in enumerate(_STEP_DEFINITIONS, start=1)
    ]


def _step_status(result: Mapping[str, Any], key: str, stage: str) -> str:
    if result.get("analysis_mode") in {"requires_parameter_confirmation", "safe_symbolic"}:
        return "unknown"
    stage_status = (result.get("stage_statuses") or {}).get(stage, {}).get("status")
    if stage_status in {"timeout", "failed"}:
        return "partial"
    if stage_status == "skipped":
        return "skipped"

    if key == "domain":
        return "complete" if result.get("domain_partition_v2", {}).get("status") == "complete" else "unknown"
    if key == "limits":
        return _collection_status(result.get("asymptotes_v2"), allow_empty=True)
    if key == "derivative":
        return "complete" if result.get("derivative") else "unknown"
    if key == "critical_points":
        return _collection_status(result.get("critical_points_v2"), allow_empty=True)
    if key == "monotonicity":
        return _contract_status(result.get("monotonicity_v2"))
    if key == "extrema":
        points = result.get("critical_points_v2") or []
        return "complete" if all(point.get("kind") != "unknown" for point in points) else "partial"
    if key == "second_derivative":
        return "complete" if result.get("second_derivative") else "unknown"
    if key == "concavity":
        return _contract_status(result.get("concavity_v2"))
    if key == "inflection_points":
        return _collection_status(result.get("inflection_points_v2"), allow_empty=True)
    if key == "intercepts":
        return _contract_status(result.get("x_intercepts_v2"))
    if key == "variation_table":
        return _contract_status(result.get("variation_table_v2"))
    return "unknown"


def _step_evidence(result: Mapping[str, Any], key: str) -> list[str]:
    if key == "domain":
        return _texts(result.get("domain_latex") or result.get("domain"))
    if key == "limits":
        asymptotes = result.get("asymptotes_v2") or {}
        return [f"{kind}: {len(asymptotes.get(kind) or [])}" for kind in ("vertical", "horizontal", "oblique")]
    if key == "derivative":
        return _texts(result.get("derivative"))
    if key in {"critical_points", "extrema"}:
        return [str(point.get("label") or point.get("kind") or point.get("x_exact")) for point in result.get("critical_points_v2") or []]
    if key == "monotonicity":
        return _segment_evidence(result.get("monotonicity_v2"))
    if key == "second_derivative":
        return _texts(result.get("second_derivative"))
    if key == "concavity":
        return _segment_evidence(result.get("concavity_v2"))
    if key == "inflection_points":
        return [str(point.get("x_exact") or point.get("x")) for point in result.get("inflection_points_v2") or []]
    if key == "intercepts":
        roots = result.get("x_intercepts_v2") or {}
        return [str(root.get("x_exact") or root.get("x")) for root in roots.get("roots") or []] + [str(item.get("set_exact")) for item in roots.get("families") or []]
    if key == "variation_table":
        table = result.get("variation_table_v2") or {}
        return [f"{segment.get('left')} → {segment.get('right')}: {segment.get('direction')}" for segment in table.get("segments") or []]
    return []


def _step_warnings(result: Mapping[str, Any], key: str, stage: str) -> list[str]:
    warnings: list[str] = []
    stage_data = (result.get("stage_statuses") or {}).get(stage) or {}
    if stage_data.get("status") in {"timeout", "failed", "skipped"}:
        warnings.append(f"Stage {stage}: {stage_data.get('status')}.")
    contract = {
        "monotonicity": result.get("monotonicity_v2"),
        "concavity": result.get("concavity_v2"),
        "intercepts": result.get("x_intercepts_v2"),
        "variation_table": result.get("variation_table_v2"),
    }.get(key)
    if isinstance(contract, Mapping):
        warnings.extend(str(item) for item in contract.get("warnings") or [])
    return list(dict.fromkeys(warnings))


def _contract_status(value: Any) -> str:
    if not isinstance(value, Mapping):
        return "unknown"
    status = value.get("status")
    return status if status in {"complete", "partial", "unknown"} else "unknown"


def _collection_status(value: Any, *, allow_empty: bool) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, (list, tuple)):
        return "complete" if value or allow_empty else "unknown"
    if isinstance(value, Mapping):
        return "complete"
    return "unknown"


def _segment_evidence(value: Any) -> list[str]:
    if not isinstance(value, Mapping):
        return []
    return [f"{segment.get('left')} → {segment.get('right')}: {segment.get('direction') or segment.get('kind')}" for segment in value.get("segments") or []]


def _texts(value: Any) -> list[str]:
    return [str(value)] if value not in (None, "") else []