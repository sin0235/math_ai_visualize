"""AI-assisted scene repair loop.

Khi ``cas_verifier.auto_fix_scene`` còn để lại các ``CasIssue`` không
deterministic (ví dụ: hệ ràng buộc phụ thuộc nhiều biến, các quan hệ phức
tạp mà optimizer cũng không hội tụ), module này gửi các issue đó dưới dạng
hint cho LLM rồi parse lại scene đầu ra. Quá trình lặp tối đa
``max_iterations`` lần, dừng sớm khi không còn issue ``error``.

Module được thiết kế **provider-agnostic**: caller truyền vào
``llm_callable`` — một hàm ``(prompt: str) -> str`` (raw JSON text). Nhờ vậy
unit test chỉ cần mock callable, còn production có thể nối với
``OpenRouterClient``, ``Router9Client``,... tuỳ runtime settings.

Quy trình:

1. Format prompt repair: scene hiện tại (JSON) + danh sách issue (text Việt).
2. Gọi ``llm_callable`` → string JSON.
3. ``build_scene_with_cas_fix`` parse + validate + auto-fix lại.
4. Nếu còn ``error`` và còn iteration → lặp.

Không tự thay scene khi LLM trả lỗi: scene gốc giữ nguyên, chỉ accumulate
warnings để frontend hiển thị.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from app.schemas.scene import MathScene
from app.services.cas_verifier import CasIssue

logger = logging.getLogger(__name__)

LLMCallable = Callable[[str], str]

_REPAIR_INSTRUCTION = (
    "Bạn là CAS repair agent. Scene JSON dưới đây vi phạm một số quan hệ hình "
    "học. Hãy chỉnh lại CHỈ toạ độ của các điểm liên quan để mọi quan hệ đều "
    "đúng về số học, GIỮ NGUYÊN cấu trúc objects/relations/annotations. Trả "
    "về JSON hợp lệ duy nhất, không kèm markdown.\n\n"
    "Yêu cầu cụ thể:\n"
    "- Không thêm/xoá object hay relation.\n"
    "- Không đổi tên điểm.\n"
    "- Có thể thay đổi x/y/z (làm tròn 6 chữ số) để thoả ràng buộc.\n"
    "- Bảo toàn tính trực quan: tránh dồn nhiều điểm trùng nhau.\n"
)


@dataclass
class RepairAttempt:
    iteration: int
    issues_before: list[CasIssue] = field(default_factory=list)
    issues_after: list[CasIssue] = field(default_factory=list)
    accepted: bool = False
    error: str | None = None


@dataclass
class RepairOutcome:
    scene: MathScene
    attempts: list[RepairAttempt] = field(default_factory=list)
    final_issues: list[CasIssue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def format_repair_prompt(scene: MathScene, issues: list[CasIssue]) -> str:
    """Format prompt cho LLM repair.

    Issues được liệt kê tóm tắt (relation_type + description) để LLM hiểu rõ
    cần sửa gì mà không phải tự suy luận lại.
    """
    scene_json = scene.model_dump(mode="json", exclude_none=True)
    issue_lines: list[str] = []
    for idx, issue in enumerate(issues, start=1):
        marker = "[ERROR]" if issue.severity == "error" else "[WARN]"
        issue_lines.append(f"{idx}. {marker} ({issue.relation_type}) {issue.description}")
    issues_block = "\n".join(issue_lines) if issue_lines else "(không có issue cụ thể)"
    return (
        f"{_REPAIR_INSTRUCTION}\n"
        f"### Issues cần sửa\n{issues_block}\n\n"
        f"### Scene hiện tại\n{json.dumps(scene_json, ensure_ascii=False, indent=2)}\n"
    )


def _filter_issues(issues: list[CasIssue], min_severity: str) -> list[CasIssue]:
    if min_severity == "error":
        return [i for i in issues if i.severity == "error" and not i.auto_fixed]
    return [i for i in issues if not i.auto_fixed]


def _parse_llm_scene(raw: str) -> dict[str, Any]:
    """Parse LLM output thành dict. Raise ValueError nếu không phải JSON hợp lệ."""
    text = raw.strip()
    if text.startswith("```"):
        # Strip code fences nếu LLM lỡ trả markdown.
        lines = text.splitlines()
        if lines:
            lines = lines[1:]  # drop opening fence
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
        text = "\n".join(lines).strip()
    return json.loads(text)


def _scene_structure(scene: MathScene) -> dict[str, Any]:
    data = scene.model_dump(
        mode="json",
        exclude_none=True,
        exclude={"scene_id", "cas_issues"},
    )

    def without_generated_ids(value: Any) -> Any:
        if isinstance(value, list):
            return [without_generated_ids(item) for item in value]
        if isinstance(value, dict):
            return {
                key: without_generated_ids(item)
                for key, item in value.items()
                if key != "id"
            }
        return value

    data = without_generated_ids(data)
    objects = data.get("objects")
    if isinstance(objects, list):
        data["objects"] = [
            {
                key: value
                for key, value in obj.items()
                if key not in {"x", "y", "z"}
            }
            if isinstance(obj, dict) and obj.get("type") in {"point_2d", "point_3d"}
            else obj
            for obj in objects
        ]
    return data


def repair_scene_iteratively(
    scene: MathScene,
    issues: list[CasIssue],
    llm_callable: LLMCallable,
    *,
    max_iterations: int = 2,
    min_severity: str = "error",
) -> RepairOutcome:
    """Lặp tối đa ``max_iterations`` lần để LLM repair scene.

    Dừng sớm nếu không còn issue thoả ``min_severity``. Nếu LLM trả output
    không parse được hoặc validate fail, attempt đó được đánh dấu
    ``accepted=False`` và scene gốc giữ nguyên.
    """
    from app.services.extractor import build_scene_with_cas_fix

    outcome = RepairOutcome(scene=scene, final_issues=list(issues))

    pending = _filter_issues(issues, min_severity)
    if not pending:
        return outcome

    current_scene = scene
    current_issues = list(issues)

    for iteration in range(1, max_iterations + 1):
        attempt = RepairAttempt(iteration=iteration, issues_before=list(current_issues))
        prompt = format_repair_prompt(current_scene, _filter_issues(current_issues, min_severity))
        try:
            raw = llm_callable(prompt)
        except Exception as exc:
            attempt.error = f"llm_callable raised: {exc!r}"
            outcome.attempts.append(attempt)
            outcome.warnings.append(f"[CAS Repair] iteration {iteration}: {attempt.error}")
            break

        try:
            scene_dict = _parse_llm_scene(raw)
        except (ValueError, json.JSONDecodeError) as exc:
            attempt.error = f"parse_failed: {exc!r}"
            outcome.attempts.append(attempt)
            outcome.warnings.append(f"[CAS Repair] iteration {iteration}: không parse được JSON ({exc!s}).")
            continue

        try:
            candidate_scene = MathScene.model_validate(scene_dict)
        except Exception as exc:
            attempt.error = f"validate_failed: {exc!r}"
            outcome.attempts.append(attempt)
            outcome.warnings.append(f"[CAS Repair] iteration {iteration}: validate scene LLM lỗi ({exc!s}).")
            continue

        if _scene_structure(candidate_scene) != _scene_structure(current_scene):
            attempt.error = "structure_changed"
            outcome.attempts.append(attempt)
            outcome.warnings.append(
                f"[CAS Repair] iteration {iteration}: LLM đã thay đổi cấu trúc scene; bỏ kết quả."
            )
            continue

        try:
            repaired_scene, repair_warnings = build_scene_with_cas_fix(scene_dict)
        except Exception as exc:
            attempt.error = f"validate_failed: {exc!r}"
            outcome.attempts.append(attempt)
            outcome.warnings.append(f"[CAS Repair] iteration {iteration}: validate scene LLM lỗi ({exc!s}).")
            continue

        from app.services.cas_verifier import verify_scene

        post_issues = verify_scene(repaired_scene)
        attempt.issues_after = post_issues
        attempt.accepted = True

        outcome.attempts.append(attempt)
        outcome.warnings.extend(repair_warnings)

        if len(_filter_issues(post_issues, min_severity)) >= len(_filter_issues(current_issues, min_severity)):
            # Không cải thiện — bỏ qua, giữ scene cũ.
            outcome.warnings.append(
                f"[CAS Repair] iteration {iteration}: LLM không giảm được số issue, giữ scene trước đó."
            )
            continue

        current_scene = repaired_scene
        current_issues = post_issues
        outcome.scene = current_scene
        outcome.final_issues = current_issues

        if not _filter_issues(current_issues, min_severity):
            break

    return outcome
