from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.core.config import Settings
from app.services.model_registry import TaskProfile
from app.services.ai_fallback import Attempt, format_attempts, text_model_candidates, text_provider_order
from app.services.openrouter_client import _build_headers as _build_openrouter_headers, _extract_message as _extract_openrouter_message
from app.services.chat_response import extract_chat_message_content
from app.services.router9_client import Router9Client, _extract_message_content as _extract_router9_message_content
from app.services.solver_service import SolverResult, SolverStep

SOLVER_EXPLAINER_SYSTEM_PROMPT = """
Bạn là giáo viên hình học không gian tiếng Việt, đang giải thích step-by-step cho học sinh lớp 12.

Quy tắc QUAN TRỌNG:
1. Giữ nguyên đáp số và kết quả cuối cùng đã cho, KHÔNG tự tính lại.
2. Mỗi bước explanation PHẢI là văn bản thuần, KHÔNG chứa LaTeX (\\frac, \\overrightarrow, v.v.) — công thức đã có trường riêng.
3. Bước 1 (Dữ liệu): PHẢI liệt kê tọa độ từng điểm liên quan lấy từ scene_objects (ví dụ: "S(0, 0, 4), A(2, 0, 0), B(0, 3, 0)").
4. Bước 2 (Công thức & vector): PHẢI nêu rõ:
   - Chọn điểm gốc nào (ví dụ: "Chọn gốc tại S")
   - Dựng những vector nào, tọa độ vector là bao nhiêu (ví dụ: "vector SA = (2, 0, -4), vector AB = (-2, 3, 0)")
   - Nếu có tích có hướng/vô hướng, ghi kết quả trung gian
   - Giải thích vì sao chọn công thức này (hai đường chéo nhau, điểm ngoài mặt phẳng, v.v.)
5. Bước 3 (Kết luận): Ghi kết quả cuối bằng văn bản (ví dụ: "Vậy d(SD,AB) = 12/5").
6. Nếu có cảnh báo (suy biến, chéo nhau, trùng), giải thích cho học sinh hiểu.

Trả về JSON thuần: {"steps":[{"index":1,"title":"...","explanation":"..."},...]}.
Không markdown, không code fence, không LaTeX trong explanation.
""".strip()


async def explain_solver_result(result: SolverResult, scene: dict[str, Any], settings: Settings, selection: TaskProfile | None = None) -> SolverResult:
    if result.answer == "Không xác định" or not result.steps:
        return result
    try:
        payload = _payload(result, scene)
        data = await _call_explainer(payload, settings, selection)
        steps_by_index = _parse_steps(data)
        if not steps_by_index:
            return result
        result.steps = [
            SolverStep(
                index=step.index,
                title=steps_by_index.get(step.index, {}).get("title") or step.title,
                explanation=steps_by_index.get(step.index, {}).get("explanation") or step.explanation,
                expression=step.expression,
                result=step.result,
                highlight=step.highlight,
                kind=step.kind,
                formula_latex=step.formula_latex,
                substitution_latex=step.substitution_latex,
                result_latex=step.result_latex,
            )
            for step in result.steps
        ]
    except Exception as error:
        result.warnings.append(f"Không gọi được LLM diễn giải, đang dùng lời giải deterministic: {error}")
    return result


def _payload(result: SolverResult, scene: dict[str, Any]) -> dict[str, Any]:
    objects = []
    point_coords: dict[str, str] = {}
    for obj in scene.get("objects", []):
        obj_type = obj.get("type")
        if obj_type in {"point_3d", "line_3d", "plane", "face", "segment"}:
            objects.append(obj)
        if obj_type == "point_3d":
            point_coords[obj["name"]] = f"({obj['x']}, {obj['y']}, {obj['z']})"
        elif obj_type == "point_2d":
            point_coords[obj["name"]] = f"({obj['x']}, {obj['y']}, 0)"

    highlight_names: list[str] = []
    for step in result.steps:
        for name in step.highlight:
            if name not in highlight_names:
                highlight_names.append(name)

    relevant_coords = {name: point_coords[name] for name in highlight_names if name in point_coords}

    return {
        "question": result.question,
        "answer": result.answer,
        "warnings": result.warnings,
        "point_coordinates": relevant_coords,
        "scene_objects": objects[:80],
        "steps": [step.to_dict() for step in result.steps],
    }


async def _call_explainer(payload: dict[str, Any], settings: Settings, selection: TaskProfile | None = None) -> dict[str, Any]:
    prompt = "Diễn giải lời giải sau cho học sinh, giữ nguyên đáp số và công thức:\n" + json.dumps(payload, ensure_ascii=False)
    attempts: list[Attempt] = []
    preferred_provider = selection.provider_id if selection else ("router9" if settings.router9_api_key else None)
    preferred_model = selection.model_id if selection else None

    for provider in text_provider_order(settings, preferred_provider):
        for model in text_model_candidates(provider, settings, preferred_model if provider == preferred_provider else None):
            selected_model = model or "<none>"
            try:
                if provider == "router9":
                    content = await _call_router9(prompt, settings, selected_model)
                elif provider == "openrouter":
                    content = await _call_openrouter_model(prompt, settings, selected_model, selected_model == "openai/gpt-oss-120b:free" or settings.openrouter_reasoning_enabled)
                elif provider == "nvidia":
                    content = await _call_nvidia(prompt, settings, selected_model)
                else:
                    continue
                return json.loads(_strip_json_fences(content))
            except Exception as error:
                attempts.append(Attempt(provider, selected_model, "solver_explainer", str(error)))

    raise RuntimeError("Không gọi được provider diễn giải solver. Đã thử: " + format_attempts(attempts))


async def _call_router9(prompt: str, settings: Settings, model: str) -> str:
    if not settings.router9_api_key or model == "<none>":
        raise RuntimeError("Chưa cấu hình 9router cho diễn giải solver.")
    client = Router9Client(settings, model=model)
    response = await client._post_chat({
        "model": model,
        "messages": [
            {"role": "system", "content": SOLVER_EXPLAINER_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "stream": False,
    })
    return _extract_router9_message_content(response)


async def _call_nvidia(prompt: str, settings: Settings, model: str) -> str:
    if not settings.nvidia_api_key:
        raise RuntimeError("NVIDIA_API_KEY chưa được cấu hình cho diễn giải solver.")
    from app.services.http_pool import TIMEOUT_FAST, get_client

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SOLVER_EXPLAINER_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "top_p": 0.95,
        "max_tokens": 8192,
    }
    headers = {"Authorization": f"Bearer {settings.nvidia_api_key}", "Content-Type": "application/json"}
    base_url = settings.nvidia_base_url.rstrip("/")
    client = get_client(base_url, TIMEOUT_FAST)
    response = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=TIMEOUT_FAST)
    if response.status_code >= 400:
        raise RuntimeError(f"NVIDIA explainer lỗi HTTP {response.status_code}: {response.text[:300]}")
    message = _extract_openrouter_message(response)
    content = extract_chat_message_content(message)
    if not content.strip():
        raise RuntimeError("NVIDIA không trả về nội dung diễn giải.")
    return content


async def _call_openrouter_model(prompt: str, settings: Settings, model: str, reasoning_enabled: bool) -> str:
    if not settings.openrouter_api_key:
        raise RuntimeError("Chưa cấu hình OpenRouter cho diễn giải solver.")
    from app.services.http_pool import TIMEOUT_FAST, get_client

    payload = {
        "model": model.removeprefix("openrouter/"),
        "messages": [
            {"role": "system", "content": SOLVER_EXPLAINER_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    if reasoning_enabled:
        payload["reasoning"] = {"enabled": True}
    base_url = settings.openrouter_base_url.rstrip("/")
    client = get_client(base_url, TIMEOUT_FAST)
    response = await client.post(f"{base_url}/chat/completions", headers=_build_openrouter_headers(settings), json=payload, timeout=TIMEOUT_FAST)
    if response.status_code >= 400:
        raise RuntimeError(f"OpenRouter explainer lỗi HTTP {response.status_code}: {response.text[:300]}")
    message = _extract_openrouter_message(response)
    content = extract_chat_message_content(message)
    if not content.strip():
        raise RuntimeError("OpenRouter không trả về nội dung diễn giải.")
    return content


def _parse_steps(data: dict[str, Any]) -> dict[int, dict[str, str]]:
    rows = data.get("steps")
    if not isinstance(rows, list):
        return {}
    parsed: dict[int, dict[str, str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        index = row.get("index")
        title = row.get("title")
        explanation = row.get("explanation")
        if isinstance(index, int) and isinstance(title, str) and isinstance(explanation, str):
            parsed[index] = {"title": title.strip(), "explanation": _sanitize_explanation(explanation)}
    return parsed


def _sanitize_explanation(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"\\overrightarrow\{([^{}]+)\}", r"vector \1", cleaned)
    cleaned = re.sub(r"\\angle\(([^)]+)\)", r"góc(\1)", cleaned)
    cleaned = re.sub(r"\\[a-zA-Z]+(?:\{[^{}]*\})*", " ", cleaned)
    cleaned = cleaned.replace("{", " ").replace("}", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _strip_json_fences(content: str) -> str:
    text = content.strip()
    if text.startswith("```json"):
        text = text.removeprefix("```json").removesuffix("```").strip()
    elif text.startswith("```"):
        text = text.removeprefix("```").removesuffix("```").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start:end + 1]
    return text
