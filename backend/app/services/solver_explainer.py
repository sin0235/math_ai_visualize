from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.core.config import Settings
from app.services.model_registry import TaskProfile
from app.services.nlp.grounding import LanguageRewrite, build_geometry_explanation_plan, validate_language_rewrites
from app.services.ai_fallback import Attempt, dedupe, format_attempts, provider_configured, text_model_candidates, text_provider_order
from app.services.openai_compat_client import OpenAICompatClient
from app.services.openrouter_client import _build_chat_payload as _build_openrouter_chat_payload, _build_headers as _build_openrouter_headers, _extract_message as _extract_openrouter_message, openrouter_api_base_url
from app.services.chat_response import extract_chat_message_content
from app.services.router9_client import Router9Client, _extract_message_content as _extract_router9_message_content
from app.services.solver_service import SolverResult, SolverStep

SOLVER_EXPLAINER_SYSTEM_PROMPT_OXYZ = """
Bạn là giáo viên hình học không gian tiếng Việt, đang giải thích step-by-step cho học sinh lớp 12. Hệ thống (máy tính) đã tính sẵn các mốc kết quả (Milestones) bằng phương pháp tọa độ hình học không gian (Oxyz) / giải tích hình học.

Quy tắc QUAN TRỌNG:
1. Bạn KHÔNG ĐƯỢC thay đổi số lượng bước chính, công thức, thế số, kết quả hoặc đáp án.
2. Bạn CHỈ ĐƯỢC viết lại `title`, `explanation` và thêm `sub_steps` giải thích bằng văn bản thuần Việt. Các `sub_steps` không được chứa công thức/số liệu mới ngoài dữ liệu đã có.
3. Bước 1 (Dữ liệu): Hãy ĐỌC KỸ `problem_text` (đề bài) trong JSON để biết hình dáng chính xác của bài toán. Hãy sử dụng sub_steps để liệt kê rõ tọa độ từng điểm liên quan phù hợp với đề bài (lấy từ scene_objects). TUYỆT ĐỐI KHÔNG tự bịa ra tính chất không có trong đề.
4. Bước 2 (Công thức & vector): Sử dụng sub_steps để trình bày việc chọn hệ trục, tính tọa độ từng vector, tính tích có hướng/vô hướng.
5. Giải thích lý do vì sao dùng công thức đó. Nếu có cảnh báo (suy biến, trùng), hãy giải thích cho học sinh hiểu.
6. Đích đến cuối cùng phải KHỚP HOÀN TOÀN với các step chính hệ thống đã cung cấp. BƯỚC CUỐI CÙNG PHẢI LÀ BƯỚC TÍNH RA ĐÁP ÁN NÀY, KHÔNG ĐƯỢC BỎ DỞ BÀI TOÁN.
7. PHẢI trả về JSON hợp lệ 100%. Tất cả các khóa (keys) và chuỗi (strings) bắt buộc phải bọc trong DẤU NGOẶC KÉP ("").

Trả về JSON thuần: 
{"steps":[{"index":1,"title":"...","explanation":"...","sub_steps":[{"index":1,"title":"...","explanation":"..."}]}]}
""".strip()

SOLVER_EXPLAINER_SYSTEM_PROMPT_CLASSICAL = """
Bạn là giáo viên hình học không gian tiếng Việt, đang giải thích step-by-step cho học sinh trung học phổ thông. Hệ thống đã tính sẵn các mốc kết quả bằng phương pháp tọa độ, nhưng NHIỆM VỤ CỦA BẠN LÀ DIỄN GIẢI LẠI THEO PHƯƠNG PHÁP HÌNH HỌC THUẦN TÚY (Hình học không gian cổ điển lớp 11).

Quy tắc QUAN TRỌNG:
1. Bạn KHÔNG ĐƯỢC thay đổi số lượng bước chính, công thức, thế số, kết quả hoặc đáp án.
2. Bạn CHỈ ĐƯỢC viết lại `title`, `explanation` và thêm `sub_steps` giải thích bằng văn bản thuần Việt. Các `sub_steps` không được chứa công thức/số liệu mới ngoài dữ liệu đã có.
3. TUYỆT ĐỐI KHÔNG nhắc đến "hệ trục tọa độ Oxyz". TUYỆT ĐỐI KHÔNG sử dụng: vector tọa độ dạng (x,y,z), phương trình tham số của đường thẳng, phương trình mặt phẳng, phương trình đại số, vector chỉ phương, vector pháp tuyến, ma trận hay định thức. Bạn ĐƯỢC phép bỏ qua hoặc gộp các bước giải tích rườm rà của hệ thống.
4. Đối với bài toán TƯƠNG GIAO (giao điểm, giao tuyến, đồng phẳng, chéo nhau): PHẢI sử dụng các tiên đề và định lý hình học không gian thuần túy (ví dụ: tìm mặt phẳng phụ, xét giao tuyến của hai mặt phẳng, đường trung bình, tỉ số đồng dạng, tính chất hình bình hành...) thay vì giải hệ phương trình đại số.
5. Hãy sử dụng các định lý hình học cổ điển (Pytago, tỉ số lượng giác, định lý Thales, đường vuông góc, hình chiếu, giao tuyến...) để lập luận logic thay vì liệt kê số liệu (0,0,0).
6. Hãy ĐỌC KỸ `problem_text` (đề bài) trong JSON để biết cấu trúc hình học chính xác (ví dụ SA vuông góc với đáy, hay hình chóp đều). TUYỆT ĐỐI KHÔNG tự bịa ra tính chất không có trong đề.
7. Đích đến cuối cùng (kết quả số học) phải KHỚP HOÀN TOÀN với đáp án số học mà hệ thống đã cung cấp. BƯỚC CUỐI CÙNG PHẢI LÀ BƯỚC TÍNH RA ĐÁP ÁN NÀY, KHÔNG ĐƯỢC BỎ DỞ BÀI TOÁN.
8. PHẢI trả về JSON hợp lệ 100%. Tất cả các khóa (keys) và chuỗi (strings) bắt buộc phải bọc trong DẤU NGOẶC KÉP ("").

Trả về JSON thuần theo cấu trúc: 
{"steps":[{"index":1,"title":"...","explanation":"...","sub_steps":[{"index":1,"title":"...","explanation":"..."}]}]}
""".strip()


async def explain_solver_result(result: SolverResult, scene: dict[str, Any], settings: Settings, selection: TaskProfile | None = None, method: str = "oxyz") -> SolverResult:
    plan = build_geometry_explanation_plan(result)
    result.grounding = plan.model_dump(mode="json")
    if result.answer == "Không xác định" or not result.steps:
        return result
    try:
        payload = _payload(result, scene)
        system_prompt = SOLVER_EXPLAINER_SYSTEM_PROMPT_CLASSICAL if method == "classical" else SOLVER_EXPLAINER_SYSTEM_PROMPT_OXYZ
        data = await _call_explainer(payload, settings, selection, system_prompt=system_prompt, method=method)
        steps_by_index = _parse_steps(data)
        if not steps_by_index:
            return result
        rewrites = validate_language_rewrites(plan, _geometry_language_rewrites(steps_by_index))
        result.steps = _merge_geometry_steps(result.steps, steps_by_index, rewrites)
        result.realization_status = "ai_validated"
        result.realization_fallback_reason = None
    except Exception as error:
        reason = _short_error(str(error))
        warning = f"Không gọi được LLM diễn giải, đang dùng lời giải deterministic: {reason}"
        result.warnings.append(warning)
        if warning not in getattr(result, "data_issues", []):
            result.data_issues.append(warning)
        result.realization_status = "fallback"
        result.realization_fallback_reason = reason
    return result


def _geometry_language_rewrites(
    steps_by_index: dict[int, dict[str, Any]],
    *,
    prefix: str = "step",
) -> list[LanguageRewrite]:
    rewrites: list[LanguageRewrite] = []
    for index, row in steps_by_index.items():
        claim_id = f"{prefix}-{index}"
        rewrites.append(
            LanguageRewrite(
                claim_id=claim_id,
                title=row.get("title"),
                explanation=row.get("explanation"),
            )
        )
        nested = {
            int(sub["index"]): sub
            for sub in row.get("sub_steps", [])
            if isinstance(sub, dict) and isinstance(sub.get("index"), int)
        }
        rewrites.extend(_geometry_language_rewrites(nested, prefix=claim_id))
    return rewrites


def _merge_geometry_steps(
    original_steps: list[SolverStep],
    steps_by_index: dict[int, dict[str, Any]],
    rewrites: dict[str, LanguageRewrite],
    *,
    prefix: str = "step",
) -> list[SolverStep]:
    merged: list[SolverStep] = []
    for step in original_steps:
        claim_id = f"{prefix}-{step.index}"
        row = steps_by_index.get(step.index, {})
        rewrite = rewrites.get(claim_id)
        nested_rows = {
            int(sub["index"]): sub
            for sub in row.get("sub_steps", [])
            if isinstance(sub, dict) and isinstance(sub.get("index"), int)
        }
        merged.append(
            SolverStep(
                index=step.index,
                title=(rewrite.title if rewrite and rewrite.title else step.title),
                explanation=(rewrite.explanation if rewrite and rewrite.explanation else step.explanation),
                expression=step.expression,
                result=step.result,
                highlight=step.highlight,
                kind=step.kind,
                formula_latex=step.formula_latex,
                substitution_latex=step.substitution_latex,
                result_latex=step.result_latex,
                sub_steps=_merge_geometry_steps(step.sub_steps, nested_rows, rewrites, prefix=claim_id),
                theorem=step.theorem,
                claim=step.claim,
                depends_on=step.depends_on,
            )
        )
    return merged

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
        "problem_text": scene.get("problem_text", ""),
        "question": result.question,
        "answer": result.answer,
        "warnings": result.warnings,
        "point_coordinates": relevant_coords,
        "scene_objects": objects[:80],
        "steps": [step.to_dict() for step in result.steps],
    }


async def _call_explainer(payload: dict[str, Any], settings: Settings, selection: TaskProfile | None = None, system_prompt: str = "", method: str = "oxyz") -> dict[str, Any]:
    if method == "classical":
        prompt = "Diễn giải lời giải sau cho học sinh. Chỉ viết lại câu chữ, không thêm dữ kiện, không đổi công thức và không đổi kết quả:\n" + json.dumps(payload, ensure_ascii=False)
    else:
        prompt = "Diễn giải lời giải sau cho học sinh. Chỉ viết lại câu chữ, giữ nguyên đáp số, công thức, thế số và kết quả:\n" + json.dumps(payload, ensure_ascii=False)
        
    attempts: list[Attempt] = []
    preferred_provider = selection.provider_id if selection else preferred_provider_from_settings(settings)
    preferred_model = selection.model_id if selection else None

    for provider in text_provider_order(settings, preferred_provider):
        candidates = text_model_candidates(provider, settings, preferred_model if provider == preferred_provider else None)
        if selection and provider == selection.provider_id:
            candidates = dedupe([*(model or "" for model in candidates), *selection.fallbacks])
        for model in candidates:
            selected_model = model or "<none>"
            try:
                if provider == "router9":
                    content = await _call_router9(prompt, settings, selected_model, system_prompt)
                elif provider == "openrouter":
                    content = await _call_openrouter_model(prompt, settings, selected_model, selected_model == "openai/gpt-oss-120b:free" or settings.openrouter_reasoning_enabled, system_prompt)
                elif provider == "nvidia":
                    content = await _call_nvidia(prompt, settings, selected_model, system_prompt)
                elif provider == "openai_compat":
                    content = await _call_openai_compat(prompt, settings, selected_model, system_prompt)
                else:
                    continue
                parsed = _strip_json_fences(content)
                if parsed is not None:
                    return parsed
                else:
                    print(f"FAILED TO PARSE JSON (json_repair returned None). RAW CONTENT:\n{content}")
                    raise ValueError("Could not parse JSON from model output")
            except Exception as error:
                attempts.append(Attempt(provider, selected_model, "solver_explainer", str(error)))

    raise RuntimeError("Không gọi được provider diễn giải solver. Đã thử: " + format_attempts(attempts))


def preferred_provider_from_settings(settings: Settings) -> str | None:
    if settings.ai_provider == "openai_compat" and provider_configured(settings.openai_compat_api_key):
        return "openai_compat"
    if provider_configured(settings.router9_api_key):
        return "router9"
    return settings.ai_provider if settings.ai_provider not in {"auto", "mock", "openrouter_gpt_oss", "opencode_nemotron"} else None


async def _call_openai_compat(prompt: str, settings: Settings, model: str, system_prompt: str) -> str:
    client = OpenAICompatClient(settings, model=model)
    return await client.chat_completion_text(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        kind="solver_explainer",
        temperature=0.2,
        max_tokens=4096,
    )


async def _call_router9(prompt: str, settings: Settings, model: str, system_prompt: str) -> str:
    if not provider_configured(settings.router9_api_key) or model == "<none>":
        raise RuntimeError("Chưa cấu hình 9router cho diễn giải solver.")
    client = Router9Client(settings, model=model)
    response = await client._post_chat({
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "stream": False,
    })
    return _extract_router9_message_content(response)


async def _call_nvidia(prompt: str, settings: Settings, model: str, system_prompt: str) -> str:
    if not provider_configured(settings.nvidia_api_key):
        raise RuntimeError("NVIDIA_API_KEY chưa được cấu hình cho diễn giải solver.")
    from app.services.http_pool import TIMEOUT_FAST, get_client

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
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
        raise RuntimeError(f"NVIDIA explainer lỗi HTTP {response.status_code}: {response.text[:300]}")
    message = _extract_openrouter_message(response)
    content = extract_chat_message_content(message)
    if not content.strip():
        raise RuntimeError("NVIDIA không trả về nội dung diễn giải.")
    return content


async def _call_openrouter_model(prompt: str, settings: Settings, model: str, reasoning_enabled: bool, system_prompt: str) -> str:
    if not provider_configured(settings.openrouter_api_key):
        raise RuntimeError("Chưa cấu hình OpenRouter cho diễn giải solver.")
    from app.services.http_pool import TIMEOUT_FAST, get_client

    payload = _build_openrouter_chat_payload(
        model,
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        request_thinking=reasoning_enabled,
        supports_thinking=None,
        supported_parameters=None,
        allow_unknown_thinking=reasoning_enabled,
    )
    base_url = openrouter_api_base_url(settings)
    client = get_client(base_url, TIMEOUT_FAST)
    response = await client.post(f"{base_url}/chat/completions", headers=_build_openrouter_headers(settings), json=payload, timeout=TIMEOUT_FAST)
    if response.status_code >= 400:
        raise RuntimeError(f"OpenRouter explainer lỗi HTTP {response.status_code}: {response.text[:300]}")
    message = _extract_openrouter_message(response)
    content = extract_chat_message_content(message)
    if not content.strip():
        raise RuntimeError("OpenRouter không trả về nội dung diễn giải.")
    return content


def _short_error(message: str) -> str:
    clean = re.sub(r"\s+", " ", message).strip()
    return clean[:240] + ("..." if len(clean) > 240 else "")


def _sanitize_latex(text: str | None) -> str | None:
    if not isinstance(text, str):
        return text
    cleaned = text.replace("°", r"^\circ")
    cleaned = cleaned.replace(r"\degree", r"^\circ")
    return cleaned


def _parse_step_node(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    index = row.get("index")
    title = row.get("title")
    explanation = row.get("explanation")
    if not (isinstance(index, int) and isinstance(title, str) and isinstance(explanation, str)):
        return None
    
    parsed = {
        "title": title.strip(),
        "explanation": _sanitize_explanation(explanation),
        "formula_latex": _sanitize_latex(row.get("formula_latex")),
        "substitution_latex": _sanitize_latex(row.get("substitution_latex")),
        "result_latex": _sanitize_latex(row.get("result_latex")),
    }
    
    sub_steps_raw = row.get("sub_steps")
    sub_steps = []
    if isinstance(sub_steps_raw, list):
        for sub_row in sub_steps_raw:
            sub = _parse_step_node(sub_row)
            if sub:
                sub["index"] = sub_row.get("index", len(sub_steps) + 1)
                sub_steps.append(sub)
    parsed["sub_steps"] = sub_steps
    return parsed


def _parse_steps(data: dict[str, Any]) -> dict[int, dict[str, Any]]:
    rows = data.get("steps")
    if not isinstance(rows, list):
        return {}
    parsed: dict[int, dict[str, Any]] = {}
    for row in rows:
        node = _parse_step_node(row)
        if node and "index" in row:
            parsed[row["index"]] = node
    return parsed


def _sanitize_explanation(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"\\overrightarrow\{([^{}]+)\}", r"vector \1", cleaned)
    cleaned = re.sub(r"\\angle\(([^)]+)\)", r"góc(\1)", cleaned)
    cleaned = re.sub(r"\\[a-zA-Z]+(?:\{[^{}]*\})*", " ", cleaned)
    cleaned = cleaned.replace("{", " ").replace("}", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned



def _strip_json_fences(content: str) -> dict[str, Any] | None:
    text = content.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        import json_repair
        # Try to repair and parse the text directly. json_repair is extremely robust
        # and will find the JSON object even if there's preamble text or broken escapes.
        parsed = json_repair.loads(text)
        if isinstance(parsed, dict):
            return parsed
        
        # If it returns a string or list, try finding the first { manually
        start = text.find("{")
        if start >= 0:
            parsed = json_repair.loads(text[start:])
            if isinstance(parsed, dict):
                return parsed
    except Exception:
        pass
        
    return None
