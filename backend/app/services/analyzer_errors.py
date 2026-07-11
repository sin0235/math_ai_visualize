from __future__ import annotations

import logging
from enum import StrEnum
from typing import Any

from fastapi import HTTPException

from app.core.logging import get_request_id


class AnalyzerErrorCode(StrEnum):
    INPUT_INVALID = "ANALYZER_INPUT_INVALID"
    PARSE_FAILED = "ANALYZER_PARSE_FAILED"
    UNSUPPORTED = "ANALYZER_UNSUPPORTED"
    COMPLEXITY_LIMIT = "ANALYZER_COMPLEXITY_LIMIT"
    TIMEOUT = "ANALYZER_TIMEOUT"
    RATE_LIMITED = "ANALYZER_RATE_LIMITED"
    OCR_FAILED = "ANALYZER_OCR_FAILED"
    INTERNAL_ERROR = "ANALYZER_INTERNAL_ERROR"
    GRAPH_FAILED = "ANALYZER_GRAPH_FAILED"


_STATUS = {
    AnalyzerErrorCode.INPUT_INVALID: 422,
    AnalyzerErrorCode.PARSE_FAILED: 422,
    AnalyzerErrorCode.UNSUPPORTED: 422,
    AnalyzerErrorCode.COMPLEXITY_LIMIT: 413,
    AnalyzerErrorCode.TIMEOUT: 504,
    AnalyzerErrorCode.RATE_LIMITED: 429,
    AnalyzerErrorCode.OCR_FAILED: 502,
    AnalyzerErrorCode.INTERNAL_ERROR: 500,
    AnalyzerErrorCode.GRAPH_FAILED: 502,
}

_MESSAGE = {
    AnalyzerErrorCode.INPUT_INVALID: "Dữ liệu yêu cầu phân tích không hợp lệ.",
    AnalyzerErrorCode.PARSE_FAILED: "Không đọc được biểu thức toán học.",
    AnalyzerErrorCode.UNSUPPORTED: "Dạng phân tích này chưa được hỗ trợ.",
    AnalyzerErrorCode.COMPLEXITY_LIMIT: "Biểu thức hoặc kết quả vượt giới hạn xử lý.",
    AnalyzerErrorCode.TIMEOUT: "Phân tích vượt giới hạn thời gian.",
    AnalyzerErrorCode.RATE_LIMITED: "Analyzer đang quá tải. Hãy thử lại sau.",
    AnalyzerErrorCode.OCR_FAILED: "Không thể đọc biểu thức từ ảnh.",
    AnalyzerErrorCode.INTERNAL_ERROR: "Analyzer gặp lỗi nội bộ.",
    AnalyzerErrorCode.GRAPH_FAILED: "Không thể dựng dữ liệu đồ thị.",
}

_RETRYABLE = {
    AnalyzerErrorCode.TIMEOUT,
    AnalyzerErrorCode.RATE_LIMITED,
    AnalyzerErrorCode.OCR_FAILED,
    AnalyzerErrorCode.INTERNAL_ERROR,
    AnalyzerErrorCode.GRAPH_FAILED,
}


def analyzer_error(
    code: AnalyzerErrorCode,
    *,
    stage: str,
    cause: object | None = None,
    partial_result: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> HTTPException:
    correlation_id = get_request_id() or ""
    if cause is not None:
        logging.getLogger("app.analyzer").error(
            "Analyzer failure code=%s stage=%s cause_type=%s",
            code.value,
            stage,
            type(cause).__name__,
            extra={"request_id": correlation_id},
        )
    detail: dict[str, Any] = {
        "code": code.value,
        "message": _MESSAGE[code],
        "correlation_id": correlation_id,
        "stage": stage,
        "retryable": code in _RETRYABLE,
    }
    if partial_result is not None:
        detail["partial_result"] = partial_result
    return HTTPException(status_code=_STATUS[code], detail=detail, headers=headers)


def analyzer_error_from_payload(data: dict[str, Any]) -> HTTPException:
    legacy_code = str(data.get("error_code") or "")
    stage = _failed_stage(data.get("stage_statuses"))
    if legacy_code == AnalyzerErrorCode.PARSE_FAILED:
        code = AnalyzerErrorCode.PARSE_FAILED
    elif legacy_code in {"ANALYZER_OUTPUT_LIMIT", AnalyzerErrorCode.COMPLEXITY_LIMIT}:
        code = AnalyzerErrorCode.COMPLEXITY_LIMIT
    elif legacy_code == AnalyzerErrorCode.TIMEOUT:
        code = AnalyzerErrorCode.TIMEOUT
    elif legacy_code == AnalyzerErrorCode.UNSUPPORTED:
        code = AnalyzerErrorCode.UNSUPPORTED
    elif legacy_code == AnalyzerErrorCode.GRAPH_FAILED:
        code = AnalyzerErrorCode.GRAPH_FAILED
    else:
        code = AnalyzerErrorCode.INTERNAL_ERROR
    return analyzer_error(code, stage=stage, cause=data.get("error"))


def _failed_stage(stage_statuses: object) -> str:
    if isinstance(stage_statuses, dict):
        for stage, payload in stage_statuses.items():
            if isinstance(payload, dict) and payload.get("status") in {"failed", "timeout"}:
                return str(stage)
    return "analyze"