"""
API routes for:
  POST /api/solve            — Step-by-step geometry solver (Lựa chọn 2)
  POST /api/analyze          — Function analysis (Lựa chọn 1)
  POST /api/analyze/ocr      — OCR image → function analysis
"""
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import require_trusted_origin
from app.core.config import get_settings, merge_runtime_settings
from app.schemas.scene import MAX_IMAGE_DATA_URL_CHARS, MAX_PROBLEM_TEXT_CHARS, RuntimeSettings
from app.services.function_analyzer import analyze_function
from app.services.function_graph_builder import build_function_graph
from app.services.ocr import extract_text_from_image
from app.services.openrouter_client import _build_headers as _build_openrouter_headers, _extract_message as _extract_openrouter_message
from app.services.router9_client import Router9Client, _extract_message_content as _extract_router9_message_content
from app.db.session import DatabaseClient, get_database
from app.services.model_registry import resolve_effective_settings
from app.services.solver_explainer import explain_solver_result
from app.services.solver_service import solve

router = APIRouter(prefix="/api", tags=["solver"])

FUNCTION_EXTRACT_PROMPT = """Từ văn bản OCR, trích xuất biểu thức hàm số.
Trả về CHỈ biểu thức dạng: x^3 - 3*x + 2
Chuyển: √→sqrt, ln→log, tg→tan, ctg→cot.
Nếu không tìm thấy, trả về: NONE

Văn bản: {text}"""


class SolveRequest(BaseModel):
    scene: dict[str, Any]
    question: str = Field(min_length=1, max_length=MAX_PROBLEM_TEXT_CHARS)
    runtime_settings: RuntimeSettings | None = None


class SolveStepResponse(BaseModel):
    index: int
    title: str
    explanation: str
    expression: str | None = None
    result: str | None = None
    highlight: list[str] = []
    kind: str | None = None
    formula_latex: str | None = None
    substitution_latex: str | None = None
    result_latex: str | None = None


class SolveResponse(BaseModel):
    question: str
    answer: str
    steps: list[SolveStepResponse]
    warnings: list[str] = []


class AnalyzeRequest(BaseModel):
    expression: str = Field(min_length=1, max_length=1000)
    parameters: dict[str, float] | None = None


class AnalyzeOcrRequest(BaseModel):
    image_data_url: str = Field(min_length=1, max_length=MAX_IMAGE_DATA_URL_CHARS)
    runtime_settings: RuntimeSettings | None = None


class CriticalPoint(BaseModel):
    x: str
    x_exact: str
    y: str | None = None
    kind: str
    kind_label: str


class VariationRow(BaseModel):
    x: str
    y: str | None = None
    kind: str
    arrow_to_next: str | None = None


class AnalyzeResponse(BaseModel):
    expression: str
    expression_latex: str | None = None
    evaluated_expression: str | None = None
    evaluated_expression_latex: str | None = None
    parameters: dict[str, Any] | None = None
    analysis_mode: str | None = None
    derivative: str | None = None
    derivative_latex: str | None = None
    second_derivative: str | None = None
    second_derivative_latex: str | None = None
    critical_points: list[CriticalPoint] = []
    inflection_points: list[dict[str, str]] = []
    intervals_increasing: list[str] = []
    intervals_decreasing: list[str] = []
    concave_up_intervals: list[str] = []
    concave_down_intervals: list[str] = []
    horizontal_asymptotes: list[dict[str, str]] = []
    vertical_asymptotes: list[dict[str, str]] = []
    oblique_asymptote: str | None = None
    x_intercepts: list[str] = []
    y_intercept: str | None = None
    variation_table: list[VariationRow] = []
    domain: str | None = None
    domain_latex: str | None = None
    range_val: str | None = None
    range_latex: str | None = None
    parity: str | None = None
    geogebra_commands: list[str] = []
    graph_scene: dict[str, Any] | None = None
    graph_points: list[dict[str, float]] = []
    ocr_text: str | None = None
    ocr_expression: str | None = None
    warnings: list[str] = []
    error: str | None = None


@router.post("/solve", response_model=SolveResponse, dependencies=[Depends(require_trusted_origin)])
async def solve_problem(request: SolveRequest, db: DatabaseClient = Depends(get_database)) -> SolveResponse:
    try:
        result = solve(request.scene, request.question)
        settings = await resolve_effective_settings(db, request.runtime_settings)
        if settings.router9_api_key or settings.openrouter_api_key:
            result = await explain_solver_result(result, request.scene, settings)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi khi giải toán: {e}") from e

    return SolveResponse(
        question=result.question,
        answer=result.answer,
        steps=[
            SolveStepResponse(
                index=s.index,
                title=s.title,
                explanation=s.explanation,
                expression=s.expression,
                result=s.result,
                highlight=s.highlight,
                kind=s.kind,
                formula_latex=s.formula_latex,
                substitution_latex=s.substitution_latex,
                result_latex=s.result_latex,
            )
            for s in result.steps
        ],
        warnings=result.warnings,
    )


@router.post("/analyze", response_model=AnalyzeResponse, dependencies=[Depends(require_trusted_origin)])
async def analyze_function_endpoint(request: AnalyzeRequest) -> AnalyzeResponse:
    try:
        data = analyze_function(request.expression, request.parameters)
        if "error" not in data:
            scene, data["geogebra_commands"], data["graph_points"] = build_function_graph(data)
            data["graph_scene"] = scene.model_dump(mode="json")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi khi phân tích hàm số: {e}") from e

    return _analysis_response(request.expression, data)


@router.post("/analyze/ocr", response_model=AnalyzeResponse, dependencies=[Depends(require_trusted_origin)])
async def analyze_from_ocr(request: AnalyzeOcrRequest) -> AnalyzeResponse:
    settings = merge_runtime_settings(get_settings(), request.runtime_settings)
    try:
        ocr_result = await extract_text_from_image(request.image_data_url, settings)
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
        raise HTTPException(status_code=400, detail=f"Lỗi khi phân tích ảnh: {e}") from e

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
        warnings=data.get("warnings", []),
    )


async def _extract_function_from_text(text: str, settings) -> str:
    content = await _chat_text(FUNCTION_EXTRACT_PROMPT.format(text=text[:MAX_PROBLEM_TEXT_CHARS]), settings)
    expression = content.strip().strip("` ")
    return expression.splitlines()[0].strip() if expression else "NONE"


async def _chat_text(prompt: str, settings) -> str:
    if settings.router9_api_key:
        models = [model for model in [settings.router9_text_model, *settings.router9_text_fallback_models] if model]
        last_error: Exception | None = None
        for model in models:
            try:
                client = Router9Client(settings, model=model)
                response = await client._post_chat({
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "stream": False,
                })
                return _extract_router9_message_content(response).strip()
            except Exception as error:
                last_error = error
        if settings.router9_only and last_error is not None:
            raise last_error

    if settings.openrouter_api_key:
        payload = {
            "model": settings.openrouter_text_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
        }
        url = f"{settings.openrouter_base_url.rstrip('/')}/chat/completions"
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(url, headers=_build_openrouter_headers(settings), json=payload)
            if response.status_code >= 400:
                raise RuntimeError(response.text)
        content = _extract_openrouter_message(response).get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()

    raise RuntimeError("Chưa cấu hình Router9 hoặc OpenRouter để gọi AI.")

