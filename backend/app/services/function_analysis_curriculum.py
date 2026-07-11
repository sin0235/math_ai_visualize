from __future__ import annotations

import copy
from typing import Any

from app.schemas.analyzer_history import CurriculumPresentation, CurriculumProfile


_STEP_ORDER = {
    10: ["domain", "parity", "intercepts", "variation", "graph"],
    11: ["domain", "periodicity", "limits", "derivative", "graph"],
    12: ["domain", "derivative", "critical_points", "monotonicity", "extrema", "concavity", "asymptotes", "variation", "graph"],
}

_TERMS = {
    10: {"domain": "Tập xác định", "variation": "Sự biến thiên", "graph": "Đồ thị"},
    11: {"periodicity": "Tính tuần hoàn", "limits": "Giới hạn", "graph": "Đồ thị"},
    12: {"derivative": "Đạo hàm", "extrema": "Cực trị", "asymptotes": "Đường tiệm cận", "variation": "Bảng biến thiên"},
}

_COMMON_MISTAKES = {
    10: ["Quên loại giá trị làm biểu thức không xác định.", "Nối đồ thị qua điểm gián đoạn."],
    11: ["Suy ra tính tuần hoàn từ vài điểm mẫu.", "Bỏ điều kiện xác định khi tính giới hạn."],
    12: ["Kết luận cực trị chỉ từ f'(x)=0.", "Nhầm giá trị lớn nhất với cận trên không đạt được."],
}

_QUESTIONS = {
    10: ["Tập xác định ảnh hưởng đồ thị thế nào?", "Đồ thị cắt các trục tại đâu?"],
    11: ["Chu kỳ cơ sở đã được chứng minh chưa?", "Giới hạn một phía nào thuộc miền xác định?"],
    12: ["Dấu đạo hàm đổi thế nào qua điểm tới hạn?", "Giá trị cực trị có đạt được không?", "Tiệm cận nào đã được kiểm chứng?"],
}


def build_curriculum_presentation(profile: CurriculumProfile, result: dict[str, Any]) -> CurriculumPresentation:
    available = [str(step.get("key")) for step in result.get("analysis_steps", []) if isinstance(step, dict)]
    preferred = _STEP_ORDER[profile.grade]
    order = [key for key in preferred if key in available]
    order.extend(key for key in available if key not in order)
    questions = _QUESTIONS[profile.grade]
    if profile.explanation_level == "concise":
        questions = questions[:1]
    return CurriculumPresentation(
        profile=profile,
        terminology=_TERMS[profile.grade],
        step_order=order,
        common_mistakes=_COMMON_MISTAKES[profile.grade],
        predicted_questions=questions,
    )


def apply_curriculum_profile(result: dict[str, Any], profile: CurriculumProfile) -> dict[str, Any]:
    output = copy.deepcopy(result)
    presentation = build_curriculum_presentation(profile, output)
    by_key = {str(step.get("key")): step for step in output.get("analysis_steps", []) if isinstance(step, dict)}
    output["analysis_steps"] = [by_key[key] for key in presentation.step_order if key in by_key]
    for index, step in enumerate(output["analysis_steps"], start=1):
        step["order"] = index
    output["curriculum_presentation"] = presentation.model_dump(mode="json")
    return output