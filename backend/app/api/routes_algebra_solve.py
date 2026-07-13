from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response

from app.api.deps import enforce_rate_limit, get_current_user, require_trusted_origin
from app.api.routes_render import enforce_render_access
from app.core.config import Settings, get_settings
from app.core.logging import get_request_id
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.admin import AdminRepository
from app.repositories.algebra_history import AlgebraHistoryRepository, compact_algebra_response_json
from app.repositories.auth import SESSION_COOKIE_NAME, SessionRepository, UserRepository
from app.schemas.algebra import (
    AlgebraExportPdfRequest,
    AlgebraHistoryCreateRequest,
    AlgebraHistoryDetail,
    AlgebraHistoryItem,
    AlgebraHistoryPatchRequest,
    AlgebraSolveRequest,
    AlgebraSolveResponse,
)
from app.schemas.nlp import InputEnvelope
from app.services.ai_resolution import resolve_byok_ai_config, settings_with_byok_connection
from app.services.algebra import solve_algebra_with_optional_ai
from app.services.algebra.circuit_breaker import algebra_circuit_breaker
from app.services.algebra.cost import algebra_request_cost, cost_exceeds_limit
from app.services.algebra.load_gate import algebra_load_gate
from app.services.algebra.pdf_export import build_algebra_pdf
from app.services.api_errors import api_error
from app.services.nlp_rollout import evaluate_configured_nlp_rollout, log_nlp_taxonomy
from app.services.user_ai_settings import UserAiSettingsError

router = APIRouter(prefix="/api/algebra", tags=["algebra"])
_DAY = 86_400


@router.post("/solve", response_model=AlgebraSolveResponse, dependencies=[Depends(require_trusted_origin)])
async def solve_algebra_endpoint(
    request: AlgebraSolveRequest,
    http_request: Request,
    db: DatabaseClient = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> AlgebraSolveResponse | JSONResponse:
    algebra_circuit_breaker.configure(
        failure_threshold=settings.algebra_circuit_failure_threshold,
        window_seconds=settings.algebra_circuit_window_seconds,
        open_seconds=settings.algebra_circuit_open_seconds,
    )
    if not algebra_circuit_breaker.allow():
        raise api_error(
            503,
            "Hệ thống đại số tạm quá tải (nhiều timeout gần đây). Vui lòng thử lại sau.",
            "ALGEBRA_CIRCUIT_OPEN",
        )

    user = await _active_user_from_request(http_request, db)
    rollout = await evaluate_configured_nlp_rollout(
        db,
        InputEnvelope(
            text=request.input,
            target="algebra",
            context={"topic": request.topic, "domain": request.domain, "variables": request.variables},
        ),
        user_id=user.id if user else None,
        request_id=get_request_id(),
        legacy_status="accepted",
        legacy_canonical=request.input,
    )
    if rollout and rollout.can_apply and rollout.candidate:
        request = _apply_algebra_canonical(request, rollout.candidate.canonical_payload)

    cost = algebra_request_cost(request)
    if cost_exceeds_limit(cost, settings.algebra_max_cost_per_request):
        raise api_error(
            429,
            f"Bài quá nặng để giải tự động (cost={cost}, max={settings.algebra_max_cost_per_request}). Hãy rút gọn đề.",
            "ALGEBRA_COST_LIMIT",
        )

    uses_ai = request.options.use_ai_extraction or request.options.ai_explanation
    await enforce_rate_limit(db, http_request, user, "algebra_solve", 60 if user else 20, 60, settings)
    daily = max(1, int(settings.algebra_daily_limit or 200))
    await enforce_rate_limit(db, http_request, user, "algebra_solve_daily", daily, _DAY, settings)
    byok_used = False
    if uses_ai:
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bạn cần đăng nhập để dùng AI nhận dạng đề đại số.")
        if settings.require_email_verification and user.email_verified_at is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn cần xác minh email trước khi dùng AI nhận dạng đề đại số.")
        await enforce_rate_limit(db, http_request, user, "algebra_ai", 20, 60)
        ai_daily = max(1, int(settings.algebra_ai_daily_limit or 50))
        await enforce_rate_limit(db, http_request, user, "algebra_ai_daily", ai_daily, _DAY, settings)
        await enforce_render_access(db, user)
        try:
            byok = await resolve_byok_ai_config(db, user, "solver", settings)
        except UserAiSettingsError as error:
            raise api_error(400, f"Cấu hình BYOK không hợp lệ: {error}", "ALGEBRA_SOLVE_FAILED") from error
        if byok is not None:
            settings = settings_with_byok_connection(settings, byok)
            byok_used = True

    limit = max(1, int(settings.algebra_max_concurrent or 8))
    slot = await algebra_load_gate.try_acquire(limit)
    if slot is None:
        raise api_error(
            429,
            "Hệ thống đang xử lý quá nhiều bài đại số. Vui lòng thử lại sau.",
            "ALGEBRA_CONCURRENT_LIMIT",
        )

    try:
        try:
            response = await solve_algebra_with_optional_ai(request, settings, load_slot=slot)
        except Exception as error:
            message = str(error)
            if user is not None:
                from app.repositories.activity import try_log_user_activity

                await try_log_user_activity(
                    db,
                    user.id,
                    "algebra.failed",
                    target_type="algebra",
                    metadata={"error": message[:200], "cost": cost},
                )
            if "timeout" in message.lower() or "ALGEBRA_TIMEOUT" in message:
                algebra_circuit_breaker.record_timeout()
                timeout_body = _timeout_payload(request, message, cost)
                return JSONResponse(status_code=504, content=timeout_body)
            raise api_error(500, "Lỗi nội bộ khi giải bài đại số.", "ALGEBRA_INTERNAL_ERROR") from error

        response.cost_score = cost
        if response.problem_type == "timeout" or any("ALGEBRA_TIMEOUT" in item for item in response.errors):
            algebra_circuit_breaker.record_timeout()
            if user is not None:
                from app.repositories.activity import try_log_user_activity

                await try_log_user_activity(
                    db,
                    user.id,
                    "algebra.failed",
                    target_type="algebra",
                    metadata={"code": "TIMEOUT", "request_id": response.request_id, "cost": cost},
                )
            return JSONResponse(status_code=504, content=response.model_dump(mode="json"))

        algebra_circuit_breaker.record_success()
        if request.domain_source == "default" and request.domain == "R":
            response.warnings = [
                "Miền R đang là mặc định; đổi sang C nếu bài số phức.",
                *response.warnings,
            ]
        if response.status == "unsupported":
            await log_nlp_taxonomy(
                db,
                user_id=user.id if user else None,
                taxonomy_code="solver_unsupported",
                target="algebra",
                status=response.status,
                request_id=response.request_id,
            )
        if response.realization_status == "fallback":
            await log_nlp_taxonomy(
                db,
                user_id=user.id if user else None,
                taxonomy_code="explainer_fallback",
                target="algebra",
                status=response.status,
                request_id=response.request_id,
            )

        if user is not None:
            from app.repositories.activity import try_log_user_activity

            await try_log_user_activity(
                db,
                user.id,
                "algebra.completed",
                target_type="algebra",
                metadata={
                    "topic": response.topic,
                    "status": response.status,
                    "request_id": response.request_id,
                    "cost": cost,
                    "timings_ms": getattr(response, "timings_ms", None),
                },
            )
            await AdminRepository(db).record_user_usage_event(
                user.id,
                "algebra_solve",
                {"topic": response.topic, "status": response.status, "request_id": response.request_id, "cost": cost},
            )
            if request.save_history:
                try:
                    history = await AlgebraHistoryRepository(db).create(
                        user.id,
                        title=None,
                        problem_preview=request.input,
                        topic=response.topic,
                        status=response.status,
                        request_id=response.request_id,
                        request_json=request.model_dump_json(),
                        response_json=compact_algebra_response_json(response.model_dump_json()),
                    )
                    response.history_id = str(history["id"])
                except Exception:
                    response.warnings = [*response.warnings, "Không lưu được lịch sử server (bỏ qua)."]
        if uses_ai and user is not None and not byok_used:
            await AdminRepository(db).record_user_usage_event(
                user.id,
                "algebra_ai",
                {
                    "use_ai_extraction": request.options.use_ai_extraction,
                    "ai_explanation": request.options.ai_explanation,
                    "request_id": response.request_id,
                },
            )
        return response
    finally:
        slot.release_http()


@router.post("/export/pdf", dependencies=[Depends(require_trusted_origin)])
async def export_algebra_pdf(
    body: AlgebraExportPdfRequest,
    http_request: Request,
    db: DatabaseClient = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> Response:
    user = await _active_user_from_request(http_request, db)
    await enforce_rate_limit(db, http_request, user, "export_algebra_pdf", 20 if user else 5, 60, settings)
    response = body.response
    if response is None and body.history_id:
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Cần đăng nhập để xuất lịch sử.")
        row = await AlgebraHistoryRepository(db).find_for_user(user.id, body.history_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lịch sử.")
        try:
            response = AlgebraSolveResponse.model_validate_json(row["response_json"])
        except Exception as error:
            raise api_error(422, "Lịch sử không đọc được.", "ALGEBRA_HISTORY_INVALID") from error
    if response is None:
        raise api_error(400, "Cần response hoặc history_id.", "ALGEBRA_EXPORT_INVALID")
    pdf_bytes = build_algebra_pdf(response)
    filename = f"algebra-{(response.request_id or 'export')[:16]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/history", response_model=list[AlgebraHistoryItem])
async def list_algebra_history(
    user: UserRecord = Depends(get_current_user),
    db: DatabaseClient = Depends(get_database),
    limit: int = 30,
    q: str | None = None,
    topic: str | None = None,
    favorite: bool | None = None,
) -> list[AlgebraHistoryItem]:
    rows = await AlgebraHistoryRepository(db).list_for_user(
        user.id, limit=limit, q=q, topic=topic, favorite=favorite
    )
    return [_history_item(row) for row in rows]


@router.post("/history", response_model=AlgebraHistoryItem, dependencies=[Depends(require_trusted_origin)])
async def create_algebra_history(
    body: AlgebraHistoryCreateRequest,
    user: UserRecord = Depends(get_current_user),
    db: DatabaseClient = Depends(get_database),
) -> AlgebraHistoryItem:
    row = await AlgebraHistoryRepository(db).create(
        user.id,
        title=body.title,
        problem_preview=body.request.input,
        topic=body.response.topic,
        status=body.response.status,
        request_id=body.response.request_id,
        request_json=body.request.model_dump_json(),
        response_json=compact_algebra_response_json(body.response.model_dump_json()),
    )
    return _history_item(row)


@router.get("/history/{item_id}", response_model=AlgebraHistoryDetail)
async def get_algebra_history(
    item_id: str,
    user: UserRecord = Depends(get_current_user),
    db: DatabaseClient = Depends(get_database),
) -> AlgebraHistoryDetail:
    row = await AlgebraHistoryRepository(db).find_for_user(user.id, item_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lịch sử.")
    response = None
    request_json: dict = {}
    try:
        response = AlgebraSolveResponse.model_validate_json(row["response_json"])
    except Exception:
        response = None
    try:
        request_json = json.loads(row["request_json"] or "{}")
    except Exception:
        request_json = {}
    item = _history_item(row)
    return AlgebraHistoryDetail(**item.model_dump(), request_json=request_json, response=response)


@router.patch("/history/{item_id}", response_model=AlgebraHistoryItem, dependencies=[Depends(require_trusted_origin)])
async def patch_algebra_history(
    item_id: str,
    body: AlgebraHistoryPatchRequest,
    user: UserRecord = Depends(get_current_user),
    db: DatabaseClient = Depends(get_database),
) -> AlgebraHistoryItem:
    row = await AlgebraHistoryRepository(db).patch_for_user(
        user.id,
        item_id,
        title=body.title,
        is_favorite=body.is_favorite,
        archive=body.archive,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lịch sử.")
    return _history_item(row)


@router.delete("/history/{item_id}", dependencies=[Depends(require_trusted_origin)])
async def delete_algebra_history(
    item_id: str,
    user: UserRecord = Depends(get_current_user),
    db: DatabaseClient = Depends(get_database),
) -> dict[str, bool]:
    ok = await AlgebraHistoryRepository(db).delete_for_user(user.id, item_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lịch sử.")
    return {"ok": True}


def _apply_algebra_canonical(request: AlgebraSolveRequest, payload: dict | None) -> AlgebraSolveRequest:
    if not payload:
        return request
    allowed = {"input", "input_format", "topic", "variables", "domain"}
    updates = {key: value for key, value in payload.items() if key in allowed}
    return AlgebraSolveRequest.model_validate({**request.model_dump(mode="python"), **updates})


def _history_item(row: dict) -> AlgebraHistoryItem:
    return AlgebraHistoryItem(
        id=str(row["id"]),
        title=row.get("title"),
        problem_preview=str(row.get("problem_preview") or ""),
        topic=str(row.get("topic") or "auto"),
        status=str(row.get("status") or "solved"),
        request_id=row.get("request_id"),
        is_favorite=bool(row.get("is_favorite")),
        archived_at=str(row["archived_at"]) if row.get("archived_at") else None,
        created_at=str(row["created_at"]) if row.get("created_at") else None,
        updated_at=str(row["updated_at"]) if row.get("updated_at") else None,
    )


def _timeout_payload(request: AlgebraSolveRequest, message: str, cost: int) -> dict:
    return AlgebraSolveResponse(
        input=request.input,
        normalized_input=request.input,
        topic=str(request.topic),
        problem_type="timeout",
        status="error",
        answer="Phép giải đại số vượt quá thời gian cho phép.",
        errors=[f"ALGEBRA_TIMEOUT: {message}"],
        warnings=["Timeout; worker process có thể đã bị terminate khi isolation bật."],
        cost_score=cost,
    ).model_dump(mode="json")


async def _active_user_from_request(request: Request, db: DatabaseClient) -> UserRecord | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    session = await SessionRepository(db).find_by_token(token)
    if session is None:
        return None
    user = await UserRepository(db).find_by_id(session.user_id)
    if user is None or user.status != "active":
        return None
    return user
