from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.config import Settings
from app.services.ai_fallback import Attempt, format_attempts, text_model_candidates, text_provider_order
from app.services.openrouter_client import _build_headers as _build_openrouter_headers, _extract_message as _extract_openrouter_message
from app.services.router9_client import Router9Client, _extract_message_content as _extract_router9_message_content
from app.services.solver_service import SolverResult, SolverStep

SOLVER_EXPLAINER_SYSTEM_PROMPT = """
Bạn là giáo viên hình học không gian tiếng Việt.
Chỉ diễn giải lại lời giải từ dữ liệu deterministic đã cho; không tự tính lại đáp số, không đổi số cuối.
Mỗi bước phải rõ: dữ kiện lấy từ hình, dữ kiện suy luận/nội suy, công thức, thế số, kết luận.
Nếu có cảnh báo hoặc trường hợp suy biến/chéo nhau/không cắt nhau, giải thích vì sao kết luận hợp lệ hoặc không hợp lệ.
Trả về JSON thuần dạng {"steps":[{"index":1,"title":"...","explanation":"..."}]}.
Không markdown, không bọc code fence.
""".strip()


async def explain_solver_result(result: SolverResult, scene: dict[str, Any], settings: Settings) -> SolverResult:
    if result.answer == "Không xác định" or not result.steps:
        return result
    try:
        payload = _payload(result, scene)
        data = await _call_explainer(payload, settings)
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
    for obj in scene.get("objects", []):
        if obj.get("type") in {"point_3d", "line_3d", "plane", "face", "segment"}:
            objects.append(obj)
    return {
        "question": result.question,
        "answer": result.answer,
        "warnings": result.warnings,
        "scene_objects": objects[:80],
        "steps": [step.to_dict() for step in result.steps],
    }


async def _call_explainer(payload: dict[str, Any], settings: Settings) -> dict[str, Any]:
    prompt = "Diễn giải lời giải sau cho học sinh, giữ nguyên đáp số và công thức:\n" + json.dumps(payload, ensure_ascii=False)
    attempts: list[Attempt] = []

    for provider in text_provider_order(settings, "router9" if settings.router9_api_key else None):
        for model in text_model_candidates(provider, settings):
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
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(f"{settings.nvidia_base_url.rstrip('/')}/chat/completions", headers=headers, json=payload)
        if response.status_code >= 400:
            raise RuntimeError(f"NVIDIA explainer lỗi HTTP {response.status_code}: {response.text[:300]}")
    message = _extract_openrouter_message(response)
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("NVIDIA không trả về nội dung diễn giải.")
    return content


async def _call_openrouter_model(prompt: str, settings: Settings, model: str, reasoning_enabled: bool) -> str:
    if not settings.openrouter_api_key:
        raise RuntimeError("Chưa cấu hình OpenRouter cho diễn giải solver.")
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
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(f"{settings.openrouter_base_url.rstrip('/')}/chat/completions", headers=_build_openrouter_headers(settings), json=payload)
        if response.status_code >= 400:
            raise RuntimeError(f"OpenRouter explainer lỗi HTTP {response.status_code}: {response.text[:300]}")
    message = _extract_openrouter_message(response)
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
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
            parsed[index] = {"title": title.strip(), "explanation": explanation.strip()}
    return parsed


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
