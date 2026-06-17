from __future__ import annotations

import json
import re

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.core.config import Settings
from app.schemas.algebra import AlgebraSolveResponse, AlgebraSolveStep
from app.services.ai_fallback import Attempt, format_attempts, provider_configured, text_model_candidates, text_provider_order
from app.services.chat_response import extract_chat_message_content
from app.services.model_provider import normalize_model_for_provider
from app.services.openrouter_client import _build_headers as _build_openrouter_headers, _extract_message as _extract_openrouter_message, openrouter_api_base_url
from app.services.router9_client import Router9Client, _extract_message_content as _extract_router9_message_content

ALGEBRA_EXPLAINER_SYSTEM_PROMPT = """
Bạn là giáo viên Toán học (Đại số, Giải tích) xuất sắc. Hệ thống máy tính (SymPy) đã giải xong bài toán và cung cấp các Cột mốc Toán học (Milestones) chắc chắn đúng.
Nhiệm vụ của bạn là SỬ DỤNG CÁC MILESTONES NÀY để VIẾT LẠI HOÀN TOÀN danh sách các bước giải (steps) sao cho thật CHI TIẾT, DỄ HIỂU, CHUẨN SƯ PHẠM.

Quy tắc bắt buộc:
1. Bạn KHÔNG BỊ GIỚI HẠN số lượng bước giải. Để giao diện gọn gàng, bạn nên dùng mảng `sub_steps` bên trong mỗi step chính. Step chính đóng vai trò là một Milestone lớn, còn `sub_steps` chứa các biến đổi nhỏ lẻ (khai triển, chuyển vế, quy đồng) để đạt được Milestone đó.
2. Tự do cung cấp công thức toán học vào `before_latex` và `after_latex` cho mỗi bước và bước con (sub-step).
3. KHÔNG ĐƯỢC làm sai lệch tập nghiệm cuối cùng. Đích đến cuối cùng phải khớp hoàn toàn với các Milestones do hệ thống cung cấp.
4. `explanation`, `rule` phải viết bằng văn bản thuần Việt Nam.
5. Chỉ trả về JSON hợp lệ theo schema yêu cầu. Không markdown.

Schema trả về:
{"steps":[{"index":1,"title":"...","explanation":"...","before_latex":"...","after_latex":"...","sub_steps":[{"index":1,"title":"...","explanation":"...","before_latex":"...","after_latex":"..."}]}]}
""".strip()


class AlgebraExplanationStep(BaseModel):
    index: int
    title: str = Field(min_length=1, max_length=120)
    explanation: str = Field(min_length=1, max_length=800)
    goal: str | None = Field(default=None, max_length=500)
    why: str | None = Field(default=None, max_length=800)
    rule: str | None = Field(default=None, max_length=300)
    operation: str | None = Field(default=None, max_length=500)
    before_latex: str | None = Field(default=None)
    after_latex: str | None = Field(default=None)
    pitfall: str | None = Field(default=None, max_length=500)
    check: str | None = Field(default=None, max_length=500)
    sub_steps: list['AlgebraExplanationStep'] = Field(default_factory=list)


class AlgebraExplanationPayload(BaseModel):
    steps: list[AlgebraExplanationStep] = Field(default_factory=list)

def _map_ai_step(step: AlgebraExplanationStep) -> AlgebraSolveStep:
    return AlgebraSolveStep(
        index=step.index,
        title=step.title,
        explanation=_sanitize_text(step.explanation),
        goal=_safe_rewrite(step.goal, None),
        why=_safe_rewrite(step.why, None),
        rule=_safe_rewrite(step.rule, None),
        operation=_safe_rewrite(step.operation, None),
        before_latex=step.before_latex,
        after_latex=step.after_latex,
        pitfall=_safe_rewrite(step.pitfall, None),
        check=_safe_rewrite(step.check, None),
        expression=None,
        expression_latex=None,
        result=None,
        result_latex=None,
        kind="solve",
        confidence="ai_generated",
        sub_steps=[_map_ai_step(sub) for sub in step.sub_steps] if step.sub_steps else [],
    )

async def explain_algebra_response_with_ai(response: AlgebraSolveResponse, settings: Settings) -> AlgebraSolveResponse:
    if not response.steps or response.status not in {"solved", "partial"}:
        return response
    if response.verification.status not in {"verified", "partially_verified"}:
        response.warnings.append("Bỏ qua AI diễn giải vì kết quả chưa được kiểm chứng đủ an toàn.")
        return response
    try:
        data = await _call_explainer(_payload(response), settings)
        payload = AlgebraExplanationPayload.model_validate(data)
        if not payload.steps:
            return response
            
        # Add the conclusion step from the original response back if it exists to preserve final verification text
        original_conclusion = next((s for s in response.steps if s.kind == "conclusion"), None)
        
        response.steps = [_map_ai_step(step) for step in payload.steps]
        
        if original_conclusion:
            original_conclusion.index = len(response.steps) + 1
            response.steps.append(original_conclusion)
            
        response.warnings.append("Đã dùng AI để sinh các bước giải chi tiết; đáp án và kiểm chứng vẫn được bảo đảm bởi hệ thống.")
    except Exception as error:
        response.warnings.append(f"Không gọi được AI diễn giải, đang dùng lời giải deterministic: {_short_error(str(error))}")
    return response


def _payload(response: AlgebraSolveResponse) -> dict:
    return {
        "input": response.input,
        "normalized_input": response.normalized_input,
        "topic": response.topic,
        "problem_type": response.problem_type,
        "status": response.status,
        "answer": response.answer,
        "answer_latex": response.answer_latex,
        "verification_status": response.verification.status,
        "verification_checks": [check.model_dump() for check in response.verification.checks],
        "assumptions": response.assumptions,
        "warnings": response.warnings,
        "milestones": response.milestones,
        "steps": [step.model_dump() for step in response.steps],
    }


async def _call_explainer(payload: dict, settings: Settings) -> dict:
    prompt = "Diễn giải lại lời giải đại số sau, giữ nguyên đáp án và công thức:\n" + json.dumps(payload, ensure_ascii=False)
    attempts: list[Attempt] = []
    for provider in text_provider_order(settings):
        candidates = text_model_candidates(provider, settings)
        for model in candidates:
            selected_model = model or "<none>"
            try:
                if provider == "router9":
                    content = await _call_router9(prompt, settings, selected_model)
                elif provider == "openrouter":
                    content = await _call_openrouter(prompt, settings, selected_model)
                elif provider == "nvidia":
                    content = await _call_nvidia(prompt, settings, selected_model)
                else:
                    continue
                return json.loads(_strip_json_fences(content))
            except (RuntimeError, json.JSONDecodeError, ValidationError, httpx.HTTPError) as error:
                attempts.append(Attempt(provider, selected_model, "algebra_explainer", str(error)))
    raise RuntimeError("Không gọi được provider diễn giải đại số. Đã thử: " + format_attempts(attempts))


async def _call_router9(prompt: str, settings: Settings, model: str) -> str:
    if not provider_configured(settings.router9_api_key) or model == "<none>":
        raise RuntimeError("Chưa cấu hình 9router cho diễn giải đại số.")
    client = Router9Client(settings, model=model)
    response = await client._post_chat({
        "model": model,
        "messages": [
            {"role": "system", "content": ALGEBRA_EXPLAINER_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "stream": False,
    })
    return _extract_router9_message_content(response)


async def _call_openrouter(prompt: str, settings: Settings, model: str) -> str:
    if not provider_configured(settings.openrouter_api_key):
        raise RuntimeError("Chưa cấu hình OpenRouter cho diễn giải đại số.")
    from app.services.http_pool import TIMEOUT_FAST, get_client

    payload = {
        "model": normalize_model_for_provider("openrouter", model),
        "messages": [
            {"role": "system", "content": ALGEBRA_EXPLAINER_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    if settings.openrouter_reasoning_enabled:
        payload["reasoning"] = {"enabled": True}
    base_url = openrouter_api_base_url(settings)
    client = get_client(base_url, TIMEOUT_FAST)
    response = await client.post(f"{base_url}/chat/completions", headers=_build_openrouter_headers(settings), json=payload, timeout=TIMEOUT_FAST)
    if response.status_code >= 400:
        raise RuntimeError(f"OpenRouter algebra explainer lỗi HTTP {response.status_code}: {response.text[:300]}")
    message = _extract_openrouter_message(response)
    content = extract_chat_message_content(message)
    if not content.strip():
        raise RuntimeError("OpenRouter không trả về nội dung diễn giải.")
    return content


async def _call_nvidia(prompt: str, settings: Settings, model: str) -> str:
    if not provider_configured(settings.nvidia_api_key):
        raise RuntimeError("NVIDIA_API_KEY chưa được cấu hình cho diễn giải đại số.")
    from app.services.http_pool import TIMEOUT_FAST, get_client

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": ALGEBRA_EXPLAINER_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "top_p": 0.95,
        "max_tokens": 4096,
    }
    headers = {"Authorization": f"Bearer {(settings.nvidia_api_key or '').strip()}", "Content-Type": "application/json"}
    base_url = settings.nvidia_base_url.rstrip("/")
    client = get_client(base_url, TIMEOUT_FAST)
    response = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=TIMEOUT_FAST)
    if response.status_code >= 400:
        raise RuntimeError(f"NVIDIA algebra explainer lỗi HTTP {response.status_code}: {response.text[:300]}")
    message = _extract_openrouter_message(response)
    content = extract_chat_message_content(message)
    if not content.strip():
        raise RuntimeError("NVIDIA không trả về nội dung diễn giải.")
    return content


def _sanitize_text(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"\\[a-zA-Z]+(?:\{[^{}]*\})*", " ", cleaned)
    cleaned = cleaned.replace("{", " ").replace("}", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _safe_rewrite(candidate: str | None, fallback: str | None) -> str | None:
    if candidate is None:
        return fallback
    cleaned = _sanitize_text(candidate)
    return cleaned or fallback


def _short_error(message: str) -> str:
    clean = re.sub(r"\s+", " ", message).strip()
    return clean[:240] + ("..." if len(clean) > 240 else "")


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
