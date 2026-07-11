from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.api.deps import enforce_rate_limit, get_current_user, require_trusted_origin
from app.api.routes_function_analysis import _analysis_response
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.activity import try_log_user_activity
from app.repositories.analyzer_history import AnalyzerHistoryRepository
from app.schemas.analysis import AnalyzeResponse, AnalyzerSessionResponse, CurriculumProfile
from app.schemas.analyzer_history import (
    AnalyzerExportRequest,
    AnalyzerHistoryCreateRequest,
    AnalyzerHistoryDetail,
    AnalyzerHistoryItem,
    AnalyzerHistoryPatchRequest,
    AnalyzerReanalyzeRequest,
    AnalyzerVersionDiff,
)
from app.services.analyzer_runtime import (
    ANALYZER_ENGINE_VERSION,
    ANALYZER_SCHEMA_VERSION,
    analysis_scope,
    create_analysis_session,
    get_analysis_session,
    run_cached_analysis,
    session_expiry_iso,
)
from app.services.function_analysis_curriculum import apply_curriculum_profile
from app.services.function_analysis_export import build_analyzer_export_document, render_analyzer_export

router = APIRouter(prefix="/api/analyzer", tags=["analyzer-history"])


@router.get("/history", response_model=list[AnalyzerHistoryItem])
async def list_analyzer_history(
    user: UserRecord = Depends(get_current_user),
    db: DatabaseClient = Depends(get_database),
    limit: int = Query(default=30, ge=1, le=100),
    q: str | None = Query(default=None, max_length=256),
    tag: str | None = Query(default=None, max_length=32),
    pinned: bool | None = Query(default=None),
    chapter: str | None = Query(default=None, max_length=96),
) -> list[AnalyzerHistoryItem]:
    rows = await AnalyzerHistoryRepository(db).list_for_user(user.id, limit=limit, q=q, tag=tag, pinned=pinned, chapter=chapter)
    return [_item(row) for row in rows]


@router.post("/history", response_model=AnalyzerHistoryItem, dependencies=[Depends(require_trusted_origin)])
async def create_analyzer_history(
    body: AnalyzerHistoryCreateRequest,
    request: Request,
    user: UserRecord = Depends(get_current_user),
    db: DatabaseClient = Depends(get_database),
) -> AnalyzerHistoryItem:
    session = _owned_session(body.analysis_id, user, request)
    result = session.result
    profile = body.curriculum_profile
    row = await AnalyzerHistoryRepository(db).create(
        user.id,
        original_expression=str(result.get("expression", "")),
        canonical_expression=str(result.get("evaluated_expression") or result.get("expression", "")),
        parameters=result.get("parameters") or {},
        window=body.window.model_dump(mode="json") if body.window else {},
        tools=body.tools.model_dump(mode="json", exclude_none=True) if body.tools else {},
        result=result,
        verification=result.get("verification") or {},
        tags=body.tags,
        pinned=body.pinned,
        grade=profile.grade,
        chapter=profile.chapter,
        explanation_level=profile.explanation_level,
        engine_version=session.engine_version,
        schema_version=session.schema_version,
    )
    await try_log_user_activity(db, user.id, "analyzer_history.created", target_type="analyzer_history", target_id=str(row["id"]))
    return _item(row)


@router.get("/history/{item_id}", response_model=AnalyzerHistoryDetail)
async def get_analyzer_history(
    item_id: str,
    request: Request,
    user: UserRecord = Depends(get_current_user),
    db: DatabaseClient = Depends(get_database),
) -> AnalyzerHistoryDetail:
    row = await AnalyzerHistoryRepository(db).find_for_user(user.id, item_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lịch sử analyzer.")
    return await _detail(row, user, request, db)


@router.patch("/history/{item_id}", response_model=AnalyzerHistoryItem, dependencies=[Depends(require_trusted_origin)])
async def patch_analyzer_history(
    item_id: str,
    body: AnalyzerHistoryPatchRequest,
    user: UserRecord = Depends(get_current_user),
    db: DatabaseClient = Depends(get_database),
) -> AnalyzerHistoryItem:
    row = await AnalyzerHistoryRepository(db).patch_for_user(
        user.id, item_id, tags=body.tags, pinned=body.pinned, chapter=body.chapter
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lịch sử analyzer.")
    return _item(row)


@router.delete("/history/{item_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_trusted_origin)])
async def delete_analyzer_history(
    item_id: str,
    user: UserRecord = Depends(get_current_user),
    db: DatabaseClient = Depends(get_database),
) -> None:
    if not await AnalyzerHistoryRepository(db).delete_for_user(user.id, item_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lịch sử analyzer.")


@router.post("/history/{item_id}/reanalyze", response_model=AnalyzerHistoryDetail, dependencies=[Depends(require_trusted_origin)])
async def reanalyze_history(
    item_id: str,
    body: AnalyzerReanalyzeRequest,
    request: Request,
    user: UserRecord = Depends(get_current_user),
    db: DatabaseClient = Depends(get_database),
) -> AnalyzerHistoryDetail:
    await enforce_rate_limit(db, request, user, "analyzer_history_reanalyze", 30, 60)
    repo = AnalyzerHistoryRepository(db)
    old = await repo.find_for_user(user.id, item_id, touch=False)
    if old is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lịch sử analyzer.")
    parameters = old.get("parameters") or {}
    parameter_values = parameters.get("active_exact") or parameters.get("active") or None
    data = await run_cached_analysis(
        str(old["original_expression"]),
        parameter_values,
        parameter_mode=(old.get("result") or {}).get("parameter_mode"),
        scope=analysis_scope(user.id, request),
        request=request,
    )
    if data.get("error"):
        raise HTTPException(status_code=422, detail="Không thể phân tích lại lịch sử này.")
    profile = body.curriculum_profile or CurriculumProfile(
        grade=old.get("grade") or 12,
        chapter=old.get("chapter") or "Khảo sát hàm số",
        explanation_level=old.get("explanation_level") or "standard",
    )
    data = apply_curriculum_profile(data, profile)
    result = _analysis_response(str(old["original_expression"]), data).model_dump(mode="json")
    row = await repo.create(
        user.id,
        original_expression=str(old["original_expression"]),
        canonical_expression=str(result.get("evaluated_expression") or result.get("expression", "")),
        parameters=result.get("parameters") or {},
        window=old.get("window") or {},
        tools=old.get("tools") or {},
        result=result,
        verification=result.get("verification") or {},
        tags=old.get("tags") or [],
        pinned=False,
        grade=profile.grade,
        chapter=profile.chapter,
        explanation_level=profile.explanation_level,
        engine_version=ANALYZER_ENGINE_VERSION,
        schema_version=ANALYZER_SCHEMA_VERSION,
        parent_history_id=item_id,
    )
    return await _detail(row, user, request, db)


@router.post("/export", dependencies=[Depends(require_trusted_origin)])
async def export_analyzer(
    body: AnalyzerExportRequest,
    request: Request,
    user: UserRecord = Depends(get_current_user),
    db: DatabaseClient = Depends(get_database),
) -> Response:
    await enforce_rate_limit(db, request, user, "analyzer_export", 30, 60)
    if body.analysis_id:
        session = _owned_session(body.analysis_id, user, request)
        result, engine_version = session.result, session.engine_version
    else:
        row = await AnalyzerHistoryRepository(db).find_for_user(user.id, body.history_id or "", touch=False)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lịch sử analyzer.")
        result, engine_version = row.get("result") or {}, str(row.get("engine_version") or "unknown")
    document = build_analyzer_export_document(
        result, engine_version=engine_version, template=body.template, profile=body.curriculum_profile
    )
    content, media_type, filename = render_analyzer_export(document, body.format)
    await try_log_user_activity(db, user.id, "analyzer_export.completed", target_type="analyzer", metadata={"format": body.format, "template": body.template})
    return Response(content=content, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def _owned_session(analysis_id: str, user: UserRecord, request: Request):
    try:
        return get_analysis_session(analysis_id, analysis_scope(user.id, request))
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error.args[0])) from error


async def _detail(row: dict[str, Any], user: UserRecord, request: Request, db: DatabaseClient) -> AnalyzerHistoryDetail:
    result = AnalyzeResponse.model_validate(row.get("result") or {})
    session = create_analysis_session(analysis_scope(user.id, request), result.model_dump(mode="json"))
    diff = None
    parent_id = row.get("parent_history_id")
    if parent_id:
        parent = await AnalyzerHistoryRepository(db).find_for_user(user.id, str(parent_id), touch=False)
        if parent:
            before = parent.get("result") or {}
            diff = AnalyzerVersionDiff(
                engine_changed=parent.get("engine_version") != row.get("engine_version"),
                schema_changed=parent.get("schema_version") != row.get("schema_version"),
                verification_changed=(before.get("verification") or {}).get("status") != (row.get("verification") or {}).get("status"),
                warning_count_before=len(before.get("warnings") or []),
                warning_count_after=len((row.get("result") or {}).get("warnings") or []),
            )
    return AnalyzerHistoryDetail(
        **_item(row).model_dump(),
        result=AnalyzerSessionResponse(
            **result.model_dump(), analysis_id=session.analysis_id, engine_version=session.engine_version, expires_at=session_expiry_iso(session)
        ),
        window=row.get("window") or {},
        tools=row.get("tools") or {},
        version_diff=diff,
    )


def _item(row: dict[str, Any]) -> AnalyzerHistoryItem:
    return AnalyzerHistoryItem(
        id=str(row["id"]),
        original_expression=str(row.get("original_expression") or ""),
        canonical_expression=str(row.get("canonical_expression") or ""),
        parameters=row.get("parameters") or {},
        tags=row.get("tags") or [],
        pinned=bool(row.get("pinned")),
        grade=row.get("grade"),
        chapter=row.get("chapter"),
        explanation_level=str(row.get("explanation_level") or "standard"),
        engine_version=str(row.get("engine_version") or "unknown"),
        schema_version=str(row.get("schema_version") or "unknown"),
        parent_history_id=row.get("parent_history_id"),
        created_at=str(row.get("created_at") or ""),
        updated_at=str(row.get("updated_at") or ""),
        last_opened_at=str(row["last_opened_at"]) if row.get("last_opened_at") else None,
    )