"""
API routes for:
  POST /api/analyze          — Function analysis (Lựa chọn 1)
  POST /api/analyze/ocr      — OCR image → function analysis
"""
from typing import Any

from fastapi import APIRouter, Depends, Request

from app.api.deps import enforce_rate_limit, require_active_user, require_trusted_origin
from app.api.routes_ocr import enforce_ocr_access
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.admin import AdminRepository
from app.schemas.analysis import AnalyzeOcrRequest, AnalyzeRequest, AnalyzeResponse, CriticalPoint, VariationRow
from app.schemas.scene import MAX_PROBLEM_TEXT_CHARS
from app.services.api_errors import api_error
from app.services.model_registry import load_model_registry, resolve_effective_settings, resolve_task_profile

router = APIRouter(prefix="/api", tags=["function-analysis"])

FUNCTION_EXTRACT_PROMPT = """Từ văn bản OCR, trích xuất biểu thức hàm số.
Trả về CHỈ biểu thức dạng: x^3 - 3*x + 2
Chuyển: √→sqrt, ln→log, tg→tan, ctg→cot.
Nếu không tìm thấy, trả về: NONE

Văn bản: {text}"""


@router.post("/analyze", response_model=AnalyzeResponse, dependencies=[Depends(require_trusted_origin)])
async def analyze_function_endpoint(request: AnalyzeRequest) -> AnalyzeResponse:
    from app.services.function_analyzer import analyze_function
    from app.services.function_graph_builder import build_function_graph

    try:
        data = analyze_function(
            request.expression,
            request.parameters,
            interval=request.interval,
            line=request.line,
            parameter_conditions=request.parameter_conditions,
            transform=request.transform,
        )
        if "error" not in data:
            scene, data["geogebra_commands"], data["graph_points"] = build_function_graph(data)
            data["graph_scene"] = scene.model_dump(mode="json")
    except Exception as e:
        raise api_error(400, f"Lỗi khi phân tích hàm số: {e}", "ANALYZE_FAILED") from e

    return _analysis_response(request.expression, data)


@router.post("/analyze/ocr", response_model=AnalyzeResponse, dependencies=[Depends(require_trusted_origin)])
async def analyze_from_ocr(
    request: AnalyzeOcrRequest,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> AnalyzeResponse:
    from app.services.function_analyzer import analyze_function
    from app.services.function_graph_builder import build_function_graph
    from app.services.ocr import extract_text_from_image

    await enforce_rate_limit(db, http_request, user, "analyze_ocr", 12, 60)
    await enforce_ocr_access(db, user)
    settings = await resolve_effective_settings(db, request.runtime_settings)
    registry = await load_model_registry(db, settings)
    ocr_profile = resolve_task_profile(registry, "ocr")
    apply_ocr_profile = ocr_profile is not None and not (
        (ocr_profile.provider_id == "openrouter" and ocr_profile.model_id == settings.openrouter_vision_model)
        or (ocr_profile.provider_id == "router9" and ocr_profile.model_id in {settings.router9_ocr_model, settings.router9_text_model})
    )
    try:
        ocr_result = await extract_text_from_image(
            request.image_data_url,
            settings,
            ocr_profile.provider_id if apply_ocr_profile and ocr_profile else None,
            ocr_profile.model_id if apply_ocr_profile and ocr_profile else None,
        )
        expression = await _extract_function_from_text(ocr_result.text, settings)
        if expression == "NONE":
            return AnalyzeResponse(expression="", error="Không tìm thấy biểu thức hàm số trong ảnh.", ocr_text=ocr_result.text, warnings=ocr_result.warnings)
        data = analyze_function(expression)
        if "error" not in data:
            scene, data["geogebra_commands"], data["graph_points"] = build_function_graph(data)
            data["graph_scene"] = scene.model_dump(mode="json")
        data["ocr_text"] = ocr_result.text
        data["ocr_expression"] = expression
        data["warnings"] = [*data.get("warnings", []), *ocr_result.warnings]
    except Exception as e:
        raise api_error(400, f"Lỗi khi phân tích ảnh: {e}", "ANALYZE_OCR_FAILED") from e

    await AdminRepository(db).record_user_usage_event(user.id, "ocr", {"source": "analyze_ocr"})
    return _analysis_response(expression, data)


def _analysis_response(expression: str, data: dict[str, Any]) -> AnalyzeResponse:
    if "error" in data:
        return AnalyzeResponse(expression=expression, error=data["error"], warnings=data.get("warnings", []), ocr_text=data.get("ocr_text"), ocr_expression=data.get("ocr_expression"))

    return AnalyzeResponse(
        expression=data["expression"],
        expression_latex=data.get("expression_latex"),
        evaluated_expression=data.get("evaluated_expression"),
        evaluated_expression_latex=data.get("evaluated_expression_latex"),
        parameters=data.get("parameters"),
        analysis_mode=data.get("analysis_mode"),
        derivative=data.get("derivative"),
        derivative_latex=data.get("derivative_latex"),
        second_derivative=data.get("second_derivative"),
        second_derivative_latex=data.get("second_derivative_latex"),
        critical_points=[CriticalPoint(**cp) for cp in data.get("critical_points", [])],
        inflection_points=data.get("inflection_points", []),
        intervals_increasing=data.get("intervals_increasing", []),
        intervals_decreasing=data.get("intervals_decreasing", []),
        concave_up_intervals=data.get("concave_up_intervals", []),
        concave_down_intervals=data.get("concave_down_intervals", []),
        horizontal_asymptotes=data.get("horizontal_asymptotes", []),
        vertical_asymptotes=data.get("vertical_asymptotes", []),
        oblique_asymptote=data.get("oblique_asymptote"),
        x_intercepts=data.get("x_intercepts", []),
        y_intercept=data.get("y_intercept"),
        variation_table=[VariationRow(**row) for row in data.get("variation_table", [])],
        domain=data.get("domain"),
        domain_latex=data.get("domain_latex"),
        range_val=data.get("range"),
        range_latex=data.get("range_latex"),
        parity=data.get("parity"),
        geogebra_commands=data.get("geogebra_commands", []),
        graph_scene=data.get("graph_scene"),
        graph_points=data.get("graph_points", []),
        ocr_text=data.get("ocr_text"),
        ocr_expression=data.get("ocr_expression"),
        interval_analysis=data.get("interval_analysis"),
        line_analysis=data.get("line_analysis"),
        parameter_conditions=data.get("parameter_conditions", []),
        transform_preview=data.get("transform_preview"),
        capabilities=data.get("capabilities"),
        warnings=data.get("warnings", []),
    )


async def _extract_function_from_text(text: str, settings) -> str:
    content = await _chat_text(FUNCTION_EXTRACT_PROMPT.format(text=text[:MAX_PROBLEM_TEXT_CHARS]), settings)
    expression = content.strip().strip("` ")
    return expression.splitlines()[0].strip() if expression else "NONE"


async def _chat_text(prompt: str, settings) -> str:
    from app.services.ai_fallback import Attempt, format_attempts, text_model_candidates, text_provider_order
    from app.services.model_provider import normalize_model_for_provider
    from app.services.openrouter_client import _build_headers as _build_openrouter_headers, _extract_message as _extract_openrouter_message
    from app.services.router9_client import Router9Client, _extract_message_content as _extract_router9_message_content

    attempts: list[Attempt] = []
    for provider in text_provider_order(settings, "router9" if settings.router9_api_key else None):
        for model in text_model_candidates(provider, settings):
            selected_model = model or "<none>"
            try:
                if provider == "router9":
                    client = Router9Client(settings, model=selected_model)
                    response = await client._post_chat({
                        "model": selected_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                        "stream": False,
                    })
                    return _extract_router9_message_content(response).strip()
                if provider == "openrouter":
                    from app.services.http_pool import TIMEOUT_FAST, get_client

                    payload = {
                        "model": normalize_model_for_provider("openrouter", selected_model),
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                    }
                    base_url = settings.openrouter_base_url.rstrip("/")
                    url = f"{base_url}/chat/completions"
                    client = get_client(base_url, TIMEOUT_FAST)
                    response = await client.post(url, headers=_build_openrouter_headers(settings), json=payload, timeout=TIMEOUT_FAST)
                    if response.status_code >= 400:
                        raise RuntimeError(response.text)
                    content = _extract_openrouter_message(response).get("content")
                    if isinstance(content, str) and content.strip():
                        return content.strip()
                    raise RuntimeError("OpenRouter không trả về nội dung text.")
            except Exception as error:
                attempts.append(Attempt(provider, selected_model, "function_extract", str(error)))

    raise RuntimeError("Chưa có provider AI gọi được. Đã thử: " + format_attempts(attempts))
