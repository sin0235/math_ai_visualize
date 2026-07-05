"""
API routes for:
  POST /api/analyze          — Function analysis (Lựa chọn 1)
  POST /api/analyze/ocr      — OCR image → function analysis
"""
import asyncio
import json
import multiprocessing as mp
import queue
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import enforce_rate_limit, require_active_user, require_trusted_origin
from app.api.routes_ocr import enforce_ocr_access, resolve_image_source
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.admin import AdminRepository
from app.schemas.analysis import AnalyzeOcrRequest, AnalyzeRequest, AnalyzeResponse, CriticalPoint, VariationRow
from app.schemas.scene import MAX_PROBLEM_TEXT_CHARS
from app.services.ai_resolution import resolve_byok_ai_config, settings_with_byok_connection
from app.services.api_errors import api_error
from app.services.model_registry import load_model_registry, resolve_effective_settings, resolve_task_profile
from app.services.user_ai_settings import UserAiSettingsError

router = APIRouter(prefix="/api", tags=["function-analysis"])

ANALYZER_TIMEOUT_SECONDS = 12
ANALYZER_COMPLEXITY_LIMIT = "ANALYZER_COMPLEXITY_LIMIT"
MAX_ANALYZER_GEOGEBRA_COMMANDS = 300
MAX_ANALYZER_GRAPH_POINTS = 500
MAX_ANALYZER_RESPONSE_CHARS = 200_000
ANALYZER_OUTPUT_LIMIT = "ANALYZER_OUTPUT_LIMIT"

FUNCTION_EXTRACT_PROMPT = """Từ văn bản OCR, trích xuất biểu thức hàm số.
Trả về CHỈ biểu thức dạng: x^3 - 3*x + 2
Chuyển: √→sqrt, ln→log, tg→tan, ctg→cot.
Nếu không tìm thấy, trả về: NONE

Văn bản: {text}"""


@router.post("/analyze", response_model=AnalyzeResponse, dependencies=[Depends(require_trusted_origin)])
async def analyze_function_endpoint(
    request: AnalyzeRequest,
    http_request: Request,
    db: DatabaseClient = Depends(get_database),
) -> AnalyzeResponse:
    await enforce_rate_limit(db, http_request, None, "analyze", 30, 60)
    data = await _run_analyzer_job(
        request.expression,
        request.parameters,
        interval=request.interval,
        line=request.line,
        parameter_conditions=request.parameter_conditions,
        transform=request.transform,
    )

    return _analysis_response(request.expression, data)


@router.post("/analyze/ocr", response_model=AnalyzeResponse, dependencies=[Depends(require_trusted_origin)])
async def analyze_from_ocr(
    request: AnalyzeOcrRequest,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> AnalyzeResponse:
    from app.services.ocr import extract_text_from_image

    await enforce_rate_limit(db, http_request, user, "analyze_ocr", 12, 60)
    await enforce_ocr_access(db, user)
    settings = await resolve_effective_settings(db, None)
    byok_used = False
    try:
        byok = await resolve_byok_ai_config(db, user, "ocr", settings)
    except UserAiSettingsError as error:
        raise api_error(400, f"Cấu hình BYOK không hợp lệ: {error}", "ANALYZE_OCR_FAILED") from error
    registry = await load_model_registry(db, settings)
    ocr_profile = resolve_task_profile(registry, "ocr")
    apply_ocr_profile = ocr_profile is not None and not (
        (ocr_profile.provider_id == "openrouter" and ocr_profile.model_id == settings.openrouter_vision_model)
        or (ocr_profile.provider_id == "router9" and ocr_profile.model_id in {settings.router9_ocr_model, settings.router9_text_model})
    )
    try:
        image_data_url = await resolve_image_source(request.image_data_url, request.upload_id, db, settings, user)
        if byok is not None and byok.client is not None:
            text = await byok.client.ocr_image(image_data_url, byok.model_id)
            from app.services.ocr import OcrResult

            settings = settings_with_byok_connection(settings, byok)
            ocr_result = OcrResult(text=text, provider="openai_compat", model=byok.model_id, warnings=["OCR sử dụng BYOK OpenAI-compatible."])
            byok_used = True
        else:
            ocr_result = await extract_text_from_image(
                image_data_url,
                settings,
                ocr_profile.provider_id if apply_ocr_profile and ocr_profile else None,
                ocr_profile.model_id if apply_ocr_profile and ocr_profile else None,
            )
        expression = await _extract_function_from_text(ocr_result.text, settings)
        if expression == "NONE":
            return AnalyzeResponse(expression="", error="Không tìm thấy biểu thức hàm số trong ảnh.", ocr_text=ocr_result.text, warnings=ocr_result.warnings)
        data = await _run_analyzer_job(expression)
        data["ocr_text"] = ocr_result.text
        data["ocr_expression"] = expression
        data["warnings"] = [*data.get("warnings", []), *ocr_result.warnings]
    except HTTPException:
        raise
    except Exception as e:
        raise api_error(400, f"Lỗi khi phân tích ảnh: {e}", "ANALYZE_OCR_FAILED") from e

    if not byok_used:
        await AdminRepository(db).record_user_usage_event(user.id, "ocr", {"source": "analyze_ocr"})
    return _analysis_response(expression, data)


async def _run_analyzer_job(
    expression: str,
    parameters: dict[str, float] | None = None,
    *,
    interval: dict[str, Any] | None = None,
    line: dict[str, Any] | None = None,
    parameter_conditions: dict[str, Any] | None = None,
    transform: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return await asyncio.to_thread(
        _run_analyzer_job_sync,
        expression,
        parameters,
        interval,
        line,
        parameter_conditions,
        transform,
    )


def _run_analyzer_job_sync(
    expression: str,
    parameters: dict[str, float] | None,
    interval: dict[str, Any] | None,
    line: dict[str, Any] | None,
    parameter_conditions: dict[str, Any] | None,
    transform: dict[str, Any] | None,
) -> dict[str, Any]:
    try:
        ctx = mp.get_context("fork")
    except ValueError:  # pragma: no cover - non-POSIX fallback
        ctx = mp.get_context()
    result_queue = ctx.Queue(maxsize=1)
    process = ctx.Process(
        target=_analyzer_worker,
        args=(result_queue, expression, parameters, interval, line, parameter_conditions, transform),
    )
    process.start()
    process.join(ANALYZER_TIMEOUT_SECONDS)
    if process.is_alive():
        process.terminate()
        process.join(1)
        return _analyzer_error("Analyzer vượt giới hạn thời gian xử lý.", ANALYZER_COMPLEXITY_LIMIT)
    try:
        status, payload = result_queue.get_nowait()
    except queue.Empty:
        return _analyzer_error("Analyzer không trả kết quả.", "ANALYZE_FAILED")
    if status == "ok":
        return payload
    return _analyzer_error(str(payload), "ANALYZE_FAILED")


def _analyzer_worker(
    result_queue,
    expression: str,
    parameters: dict[str, float] | None,
    interval: dict[str, Any] | None,
    line: dict[str, Any] | None,
    parameter_conditions: dict[str, Any] | None,
    transform: dict[str, Any] | None,
) -> None:
    try:
        from app.services.function_analyzer import analyze_function
        from app.services.function_graph_builder import build_function_graph

        data = analyze_function(
            expression,
            parameters,
            interval=interval,
            line=line,
            parameter_conditions=parameter_conditions,
            transform=transform,
        )
        if "error" not in data:
            scene, data["geogebra_commands"], data["graph_points"] = build_function_graph(data)
            data["graph_scene"] = scene.model_dump(mode="json")
        data.pop("_parsed_expr", None)
        data.pop("_evaluated_expr", None)
        result_queue.put(("ok", _apply_analyzer_output_limits(data)))
    except Exception as error:  # pragma: no cover - child-process defensive path
        result_queue.put(("error", f"Lỗi khi phân tích hàm số: {error}"))


def _apply_analyzer_output_limits(data: dict[str, Any]) -> dict[str, Any]:
    commands = data.get("geogebra_commands") or []
    if len(commands) > MAX_ANALYZER_GEOGEBRA_COMMANDS:
        return _analyzer_error("Analyzer tạo quá nhiều lệnh GeoGebra.", ANALYZER_OUTPUT_LIMIT)
    points = data.get("graph_points") or []
    if len(points) > MAX_ANALYZER_GRAPH_POINTS:
        return _analyzer_error("Analyzer tạo quá nhiều điểm đồ thị.", ANALYZER_OUTPUT_LIMIT)
    response_chars = len(json.dumps(data, ensure_ascii=False, default=str))
    if response_chars > MAX_ANALYZER_RESPONSE_CHARS:
        return _analyzer_error("Analyzer tạo phản hồi quá lớn.", ANALYZER_OUTPUT_LIMIT)
    return data


def _analyzer_error(message: str, code: str) -> dict[str, Any]:
    return {"error": message, "error_code": code, "warnings": [message]}


def _analysis_response(expression: str, data: dict[str, Any]) -> AnalyzeResponse:
    if "error" in data:
        return AnalyzeResponse(expression=expression, error=data["error"], error_code=data.get("error_code"), warnings=data.get("warnings", []), ocr_text=data.get("ocr_text"), ocr_expression=data.get("ocr_expression"))

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
        complexity_score=data.get("complexity_score"),
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
                if provider == "openai_compat":
                    from app.services.openai_compat_client import OpenAICompatClient

                    return (await OpenAICompatClient(settings, model=selected_model).chat_completion_text(
                        [{"role": "user", "content": prompt}],
                        kind="function_extract",
                        temperature=0.1,
                        max_tokens=512,
                    )).strip()
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
