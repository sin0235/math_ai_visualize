from __future__ import annotations

import json
import re

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.core.config import Settings
from app.schemas.algebra import AlgebraSolveRequest, AlgebraTopic
from app.services.ai_fallback import Attempt, format_attempts, provider_configured, text_model_candidates, text_provider_order
from app.services.chat_response import extract_chat_message_content
from app.services.model_provider import normalize_model_for_provider
from app.services.openai_compat_client import OpenAICompatClient
from app.services.openrouter_client import _build_headers as _build_openrouter_headers, _extract_message as _extract_openrouter_message, openrouter_api_base_url
from app.services.router9_client import Router9Client, _extract_message_content as _extract_router9_message_content

ALGEBRA_EXTRACTION_SYSTEM_PROMPT = """
Bạn là bộ trích xuất đề Đại số C3 tiếng Việt sang JSON cho solver deterministic.
Chỉ trả về JSON hợp lệ, không markdown, không giải thích, không giải bài.

Schema bắt buộc:
{
  "input": string,
  "input_format": "plain" | "structured",
  "topic": "equation" | "inequality" | "exponential_log" | "trigonometry" | "complex" | "sequence" | "combinatorics_probability" | "system" | "parameter" | "calculus_derivative" | "calculus_derivative_by_definition" | "calculus_limit" | "calculus_continuous_at" | "calculus_integral",
  "variables": [string],
  "parameters": [string],
  "domain": "R" | "C" | "N" | "Z",
  "warnings": [string]
}

Quy tắc:
1. KHÔNG tính nghiệm, KHÔNG sinh answer, KHÔNG sinh steps.
2. input phải là dạng solver đã hỗ trợ, ví dụ:
   - phương trình: x^2 - 5*x + 6 = 0
   - hệ: x+y=3; x-y=1
   - tổ hợp: C(10,3), A(5,2), factorial(5), coefficient((1+x)^5,x,3)
   - cấp số: arithmetic(u1=2,d=3,n=10), arithmetic_sum(...), geometric(...), geometric_sum(...)
   - tham số: quadratic_double_root(a=1,b=-2*m,c=1,var=x,param=m), quadratic_has_two_roots(...), quadratic_has_real_root(...), quadratic_no_real_root(...), quadratic_positive_all(...)
   - giải tích: derivative(expr=x^2,var=x), derivative_by_definition(expr=x^2,var=x,at=2), limit(expr=(x^2-1)/(x-1),var=x,to=1), continuous_at(expr=Piecewise((x^2,x>=1),(2*x-1,x<1)),var=x,at=1), integral(expr=2*x,var=x,a=0,b=1)
3. Nếu đề hỏi "tìm m để phương trình bậc hai có nghiệm kép", dùng quadratic_double_root.
4. Nếu đề hỏi "có hai nghiệm phân biệt", dùng quadratic_has_two_roots.
5. Nếu đề hỏi "có nghiệm thực", dùng quadratic_has_real_root.
6. Nếu đề hỏi "vô nghiệm thực", dùng quadratic_no_real_root.
7. Nếu đề hỏi "tam thức/phương trình dương với mọi x", dùng quadratic_positive_all.
8. Dùng * cho phép nhân, ^ cho lũy thừa, không dùng LaTeX trong input.
9. Nếu không chắc, vẫn trả JSON gần nhất và thêm cảnh báo trong warnings.
""".strip()


class AlgebraExtractionPayload(BaseModel):
    input: str = Field(min_length=1, max_length=2_000)
    input_format: str = "plain"
    topic: AlgebraTopic
    variables: list[str] = Field(default_factory=list)
    parameters: list[str] = Field(default_factory=list)
    domain: str = "R"
    warnings: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


async def extract_algebra_request_with_ai(problem_text: str, base_request: AlgebraSolveRequest, settings: Settings) -> tuple[AlgebraSolveRequest, list[str]]:
    data = await _call_extractor(problem_text, settings)
    payload = AlgebraExtractionPayload.model_validate(data)
    if payload.topic == "auto":
        raise ValueError("AI extraction phải trả về topic cụ thể, không dùng auto.")
    if payload.input_format not in {"plain", "structured"}:
        raise ValueError("AI extraction chỉ được trả input_format plain hoặc structured.")
    if payload.domain not in {"R", "C", "N", "Z"}:
        raise ValueError("AI extraction trả domain không hợp lệ.")
    request = AlgebraSolveRequest(
        input=payload.input,
        input_format=payload.input_format,  # type: ignore[arg-type]
        topic=payload.topic,
        variables=payload.variables,
        parameters=payload.parameters,
        domain=payload.domain,  # type: ignore[arg-type]
        interval=base_request.interval,
        options=base_request.options,
    )
    warnings = ["Đã dùng AI để diễn giải đề sang input chuẩn; đáp án vẫn do solver deterministic và verifier tạo."]
    warnings.extend(payload.warnings)
    return request, warnings


async def _call_extractor(problem_text: str, settings: Settings) -> dict:
    prompt = "Đề bài cần trích xuất:\n" + problem_text.strip()
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
                elif provider == "openai_compat":
                    content = await _call_openai_compat(prompt, settings, selected_model)
                else:
                    continue
                return json.loads(_strip_json_fences(content))
            except (RuntimeError, json.JSONDecodeError, ValidationError, httpx.HTTPError) as error:
                attempts.append(Attempt(provider, selected_model, "algebra_extraction", str(error)))
    raise RuntimeError("Không gọi được AI extraction cho đại số. Đã thử: " + format_attempts(attempts))


async def _call_openai_compat(prompt: str, settings: Settings, model: str) -> str:
    client = OpenAICompatClient(settings, model=model)
    return await client.chat_completion_text(
        [
            {"role": "system", "content": ALGEBRA_EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        kind="algebra_extraction",
        temperature=0,
        max_tokens=2048,
    )


async def _call_router9(prompt: str, settings: Settings, model: str) -> str:
    if not provider_configured(settings.router9_api_key) or model == "<none>":
        raise RuntimeError("Chưa cấu hình 9router cho algebra extraction.")
    client = Router9Client(settings, model=model)
    response = await client._post_chat({
        "model": model,
        "messages": [
            {"role": "system", "content": ALGEBRA_EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "stream": False,
    })
    return _extract_router9_message_content(response)


async def _call_openrouter(prompt: str, settings: Settings, model: str) -> str:
    if not provider_configured(settings.openrouter_api_key):
        raise RuntimeError("Chưa cấu hình OpenRouter cho algebra extraction.")
    from app.services.http_pool import TIMEOUT_FAST, get_client

    payload = {
        "model": normalize_model_for_provider("openrouter", model),
        "messages": [
            {"role": "system", "content": ALGEBRA_EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
    }
    if settings.openrouter_reasoning_enabled:
        payload["reasoning"] = {"enabled": True}
    base_url = openrouter_api_base_url(settings)
    client = get_client(base_url, TIMEOUT_FAST)
    response = await client.post(f"{base_url}/chat/completions", headers=_build_openrouter_headers(settings), json=payload, timeout=TIMEOUT_FAST)
    if response.status_code >= 400:
        raise RuntimeError(f"OpenRouter algebra extraction lỗi HTTP {response.status_code}: {response.text[:300]}")
    message = _extract_openrouter_message(response)
    content = extract_chat_message_content(message)
    if not content.strip():
        raise RuntimeError("OpenRouter không trả về nội dung extraction.")
    return content


async def _call_nvidia(prompt: str, settings: Settings, model: str) -> str:
    if not provider_configured(settings.nvidia_api_key):
        raise RuntimeError("NVIDIA_API_KEY chưa được cấu hình cho algebra extraction.")
    from app.services.http_pool import TIMEOUT_FAST, get_client

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": ALGEBRA_EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "top_p": 0.95,
        "max_tokens": 2048,
    }
    headers = {"Authorization": f"Bearer {(settings.nvidia_api_key or '').strip()}", "Content-Type": "application/json"}
    base_url = settings.nvidia_base_url.rstrip("/")
    client = get_client(base_url, TIMEOUT_FAST)
    response = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=TIMEOUT_FAST)
    if response.status_code >= 400:
        raise RuntimeError(f"NVIDIA algebra extraction lỗi HTTP {response.status_code}: {response.text[:300]}")
    message = _extract_openrouter_message(response)
    content = extract_chat_message_content(message)
    if not content.strip():
        raise RuntimeError("NVIDIA không trả về nội dung extraction.")
    return content


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
