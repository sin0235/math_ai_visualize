"""Reverse: sinh N đề bài biến thể từ một MathScene cho trước.

Use case: giáo viên có một hình hình học (đã dựng), muốn sinh ra nhiều đề bài
"tương đương cấu trúc nhưng khác số liệu/biến số" để tránh học sinh chép bài
nhau.

Cách làm: serialise MathScene → JSON, gửi cho LLM với system prompt yêu cầu giữ
nguyên *cấu trúc hình học* (cùng dạng hình chóp, cùng quan hệ vuông góc/song
song) nhưng thay đổi:
- Tên điểm (S.ABCD ↔ M.NPQR ↔ A.BCDE).
- Số liệu (cạnh, góc, bán kính) trong khoảng hợp lý.
- Câu hỏi (tính thể tích, khoảng cách, góc, chứng minh…).

LLM trả về một danh sách các chuỗi đề bài tiếng Việt.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

from app.core.config import Settings
from app.services.ai_fallback import Attempt, format_attempts, provider_configured, text_model_candidates, text_provider_order
from app.services.model_provider import normalize_model_for_provider
from app.services.openai_compat_client import OpenAICompatClient
from app.services.openrouter_client import _build_headers, _extract_message, _format_openrouter_error, _strip_json_fences, openrouter_api_base_url
from app.services.provider_logging import log_provider_request, log_provider_response
from app.services.chat_response import extract_chat_message_content
from app.services.router9_client import Router9Client, _extract_message_content as _extract_router9_message_content

VARIANTS_SYSTEM_PROMPT = """
Bạn là giáo viên Toán THPT chuyên ra đề.
Cho trước một MathScene JSON mô tả hình hình học. Hãy sinh ra N đề toán
TƯƠNG ĐƯƠNG VỀ CẤU TRÚC nhưng khác nhau để mỗi học sinh nhận một đề khác.

Quy tắc:
1. Giữ nguyên cấu hình hình (cùng loại đa diện, cùng các quan hệ vuông
   góc/song song/đối xứng).
2. Có thể đổi:
   - Tên điểm (S.ABCD → M.NPQR → P.ABCD…).
   - Số liệu (cạnh đáy, chiều cao, bán kính, góc) trong khoảng số nguyên/đơn
     giản (ví dụ: 2..10, hoặc các giá trị đặc biệt như sqrt(2), sqrt(3)).
   - Câu hỏi cuối: tính thể tích / diện tích / khoảng cách / góc / chứng minh.
3. KHÔNG đổi: dạng đa diện, cấu hình đáy (vuông/đều/cân/thường), quan hệ
   "SA vuông góc đáy" hay "S.ABCD đều".
4. Mỗi đề là một đoạn văn hoàn chỉnh, kết thúc bằng câu hỏi rõ ràng.
5. Không suy luận, không giải, không markdown, không bullet trong từng đề.

Định dạng output bắt buộc: JSON object với khoá "variants" là mảng N chuỗi:
{
  "variants": ["Đề 1...", "Đề 2...", ...]
}
""".strip()


@dataclass(frozen=True)
class VariantsResult:
    variants: list[str]
    provider: str
    model: str


def _build_user_prompt(scene: dict, original_problem: str | None, count: int) -> str:
    parts = [
        f"Số đề cần sinh: {count}.",
        "MathScene v3 gốc (JSON):",
        json.dumps(scene, ensure_ascii=False, indent=2),
    ]
    if original_problem:
        parts.extend(["", "Đề bài gốc (tham khảo phong cách):", original_problem.strip()])
    parts.append('\nHãy trả về JSON đúng định dạng {"variants": [...]} với đúng ' + str(count) + " đề.")
    return "\n".join(parts)


async def _call_variants_provider(provider: str, model: str, user_prompt: str, settings: Settings) -> str:
    if provider == "router9":
        client = Router9Client(settings, model=model)
        response = await client._post_chat({
            "model": model,
            "messages": [
                {"role": "system", "content": VARIANTS_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.6,
            "stream": False,
        })
        return _extract_router9_message_content(response)

    if provider == "openrouter":
        return await _call_openrouter_variants(model, user_prompt, settings)

    if provider == "nvidia":
        return await _call_nvidia_variants(model, user_prompt, settings)

    if provider == "openai_compat":
        return await _call_openai_compat_variants(model, user_prompt, settings)

    raise RuntimeError(f"Provider không hỗ trợ sinh biến thể: {provider}")


async def _call_openai_compat_variants(model: str, user_prompt: str, settings: Settings) -> str:
    client = OpenAICompatClient(settings, model=model)
    return await client.chat_completion_text(
        [
            {"role": "system", "content": VARIANTS_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        kind="variants",
        temperature=0.6,
        max_tokens=8192,
        problem_chars=len(user_prompt),
    )


async def _call_openrouter_variants(model: str, user_prompt: str, settings: Settings) -> str:
    if not provider_configured(settings.openrouter_api_key):
        raise RuntimeError("OPENROUTER_API_KEY chưa được cấu hình để sinh đề biến thể.")
    payload = {
        "model": normalize_model_for_provider("openrouter", model),
        "messages": [
            {"role": "system", "content": VARIANTS_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.6,
    }
    from app.services.http_pool import TIMEOUT_SCENE, get_client

    base_url = openrouter_api_base_url(settings)
    url = f"{base_url}/chat/completions"
    started_at = time.perf_counter()
    log_provider_request("openrouter", "variants", url, payload["model"], problem_chars=len(user_prompt))
    client = get_client(base_url, TIMEOUT_SCENE)
    response = await client.post(url, headers=_build_headers(settings), json=payload, timeout=TIMEOUT_SCENE)
    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    log_provider_response("openrouter", "variants", response.status_code, elapsed_ms, len(response.text))
    if response.status_code >= 400:
        raise RuntimeError(_format_openrouter_error(response))
    content = extract_chat_message_content(_extract_message(response))
    if not content.strip():
        raise RuntimeError("Provider không trả về nội dung biến thể.")
    return content


async def _call_nvidia_variants(model: str, user_prompt: str, settings: Settings) -> str:
    if not provider_configured(settings.nvidia_api_key):
        raise RuntimeError("NVIDIA_API_KEY chưa được cấu hình để sinh đề biến thể.")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": VARIANTS_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.6,
        "top_p": 0.95,
        "max_tokens": 8192,
    }
    headers = {"Authorization": f"Bearer {(settings.nvidia_api_key or '').strip()}", "Content-Type": "application/json"}
    from app.services.http_pool import TIMEOUT_SCENE, get_client

    base_url = settings.nvidia_base_url.rstrip("/")
    url = f"{base_url}/chat/completions"
    started_at = time.perf_counter()
    log_provider_request("nvidia", "variants", url, payload["model"], problem_chars=len(user_prompt))
    client = get_client(base_url, TIMEOUT_SCENE)
    response = await client.post(url, headers=headers, json=payload, timeout=TIMEOUT_SCENE)
    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    log_provider_response("nvidia", "variants", response.status_code, elapsed_ms, len(response.text))
    if response.status_code >= 400:
        raise RuntimeError(f"NVIDIA variants lỗi HTTP {response.status_code}: {response.text[:300]}")
    content = extract_chat_message_content(_extract_message(response))
    if not content.strip():
        raise RuntimeError("NVIDIA không trả về nội dung biến thể.")
    return content


def _parse_variants(content: str, count: int) -> list[str]:
    try:
        parsed = json.loads(_strip_json_fences(content))
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Provider trả JSON biến thể không hợp lệ: {error.msg}") from error

    raw_variants = parsed.get("variants")
    if not isinstance(raw_variants, list):
        raise RuntimeError("Provider không trả về trường 'variants' hợp lệ.")

    cleaned: list[str] = []
    for item in raw_variants:
        if isinstance(item, str):
            text = item.strip()
            if len(text) >= 20:
                cleaned.append(text)
    if not cleaned:
        raise RuntimeError("Không có biến thể đủ dài (tối thiểu 20 ký tự).")
    return cleaned[:count]


async def generate_variants(
    scene: dict,
    settings: Settings,
    count: int = 3,
    original_problem: str | None = None,
    explicit_model: str | None = None,
    preferred_provider: str | None = "openrouter",
) -> VariantsResult:
    if count < 1 or count > 10:
        raise ValueError("Số biến thể phải từ 1 đến 10.")

    user_prompt = _build_user_prompt(scene, original_problem, count)
    attempts: list[Attempt] = []
    for provider in text_provider_order(settings, preferred_provider):
        for model in text_model_candidates(provider, settings, explicit_model if provider == preferred_provider else None):
            selected_model = model or "<none>"
            try:
                content = await _call_variants_provider(provider, selected_model, user_prompt, settings)
                variants = _parse_variants(content, count)
                return VariantsResult(variants=variants, provider=provider, model=selected_model)
            except Exception as error:
                attempts.append(Attempt(provider, selected_model, "variants", str(error)))

    raise RuntimeError("Sinh đề biến thể thất bại qua tất cả provider. Đã thử: " + format_attempts(attempts))


__all__ = ["VariantsResult", "generate_variants", "VARIANTS_SYSTEM_PROMPT"]
