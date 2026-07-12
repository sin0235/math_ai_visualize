"""API xuất committed MathScene v3 sang TikZ, GGB, PDF và ảnh."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Request, Response

from app.api.deps import enforce_rate_limit, require_active_user, require_trusted_origin
from app.api.routes_render import enforce_render_access
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.renderers.projection_export_v3 import (
    build_ggb_v3,
    build_image_v3,
    build_katex_html_v3,
    build_pdf_v3,
    build_tikz_document_v3,
)
from app.repositories.activity import try_log_user_activity
from app.schemas.scene_v3 import SceneExportRequestV3
from app.services.api_errors import api_error
from app.services.committed_scene_v3 import CommittedSceneError, load_committed_scene_v3

router = APIRouter(prefix="/api/export", tags=["export"])


async def _load_export(
    request: SceneExportRequestV3,
    user: UserRecord,
    db: DatabaseClient,
):
    try:
        return await load_committed_scene_v3(db, user.id, request.scene_ref)
    except CommittedSceneError as error:
        raise api_error(error.status_code, str(error), error.code) from error


async def _prepare_export(
    request: SceneExportRequestV3,
    http_request: Request,
    user: UserRecord,
    db: DatabaseClient,
    fmt: str,
):
    await enforce_rate_limit(db, http_request, user, f"export_{fmt}", 30 if user else 8, 60)
    await enforce_render_access(db, user)
    return await _load_export(request, user, db)


async def _finish_export(db: DatabaseClient, user: UserRecord, fmt: str) -> None:
    await try_log_user_activity(db, user.id, "export.completed", target_type="export", metadata={"format": fmt})


@router.post("/tikz", dependencies=[Depends(require_trusted_origin)])
async def export_tikz(
    request: SceneExportRequestV3,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> Response:
    committed = await _prepare_export(request, http_request, user, db, "tikz")
    body = await asyncio.to_thread(
        build_tikz_document_v3,
        committed.result.projection,
        committed.result.scene.problem_text,
    )
    await _finish_export(db, user, "tikz")
    return _file_response(body, "application/x-tex", "math-renderer.tex")


@router.post("/ggb", dependencies=[Depends(require_trusted_origin)])
async def export_ggb(
    request: SceneExportRequestV3,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> Response:
    committed = await _prepare_export(request, http_request, user, db, "ggb")
    body = await asyncio.to_thread(
        build_ggb_v3,
        committed.result.projection,
        committed.result.scene.problem_text,
    )
    await _finish_export(db, user, "ggb")
    return _file_response(body, "application/vnd.geogebra.file", "math-renderer.ggb")


@router.post("/pdf", dependencies=[Depends(require_trusted_origin)])
async def export_pdf(
    request: SceneExportRequestV3,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> Response:
    committed = await _prepare_export(request, http_request, user, db, "pdf")
    try:
        body = await asyncio.to_thread(
            build_pdf_v3,
            committed.result.projection,
            committed.result.scene.problem_text,
            request.view_capture,
        )
    except ValueError as error:
        raise api_error(400, str(error), "EXPORT_VIEW_CAPTURE_INVALID") from error
    await _finish_export(db, user, "pdf")
    return _file_response(body, "application/pdf", "math-renderer.pdf")


async def _export_image(
    request: SceneExportRequestV3,
    http_request: Request,
    user: UserRecord,
    db: DatabaseClient,
    fmt: str,
) -> Response:
    committed = await _prepare_export(request, http_request, user, db, fmt)
    body = await asyncio.to_thread(
        build_image_v3,
        committed.result.projection,
        committed.result.scene.problem_text,
        fmt,
    )
    await _finish_export(db, user, fmt)
    media_type = {"png": "image/png", "jpg": "image/jpeg", "svg": "image/svg+xml; charset=utf-8"}[fmt]
    return _file_response(body, media_type, f"math-renderer.{fmt}")


@router.post("/png", dependencies=[Depends(require_trusted_origin)])
async def export_png(
    request: SceneExportRequestV3,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> Response:
    return await _export_image(request, http_request, user, db, "png")


@router.post("/jpg", dependencies=[Depends(require_trusted_origin)])
async def export_jpg(
    request: SceneExportRequestV3,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> Response:
    return await _export_image(request, http_request, user, db, "jpg")


@router.post("/svg", dependencies=[Depends(require_trusted_origin)])
async def export_svg(
    request: SceneExportRequestV3,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> Response:
    return await _export_image(request, http_request, user, db, "svg")


@router.post("/katex-html", dependencies=[Depends(require_trusted_origin)])
async def export_katex_html(
    request: SceneExportRequestV3,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> Response:
    committed = await _prepare_export(request, http_request, user, db, "katex-html")
    body = await asyncio.to_thread(
        build_katex_html_v3,
        committed.result.projection,
        committed.result.scene.problem_text,
    )
    await _finish_export(db, user, "katex-html")
    return _file_response(body, "text/html; charset=utf-8", "math-renderer-katex.html")


def _file_response(content: bytes | str, media_type: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )