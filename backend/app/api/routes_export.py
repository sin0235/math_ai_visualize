"""API xuất scene sang TikZ / GGB / PDF.

Body chung: ``SceneRenderRequest`` (đã có) → endpoint trả về file binary/text
tương ứng. Frontend sẽ tải về cho user.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Request, Response

from app.api.deps import enforce_rate_limit, require_active_user, require_trusted_origin
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.schemas.scene import MathScene, SceneRenderRequest
from app.api.routes_render import enforce_render_access

router = APIRouter(prefix="/api/export", tags=["export"])


def _safe_export_scene(request: SceneRenderRequest) -> MathScene:
    from fastapi import status

    from app.services.api_errors import api_error
    from app.services.geometry_engine import normalize_scene
    from app.services.render_quality_gate import assert_render_response_safe_for_downstream, assert_scene_safe_for_downstream

    try:
        if request.response is not None:
            assert_render_response_safe_for_downstream(
                request.response,
                request.scene,
                operation="xuất file",
                allow_partial=True,
            )
            return normalize_scene(request.scene, request.advanced_settings)
        assert_scene_safe_for_downstream(request.scene, operation="xuất file", allow_partial=True)
        return normalize_scene(request.scene, request.advanced_settings)
    except ValueError as error:
        code = "RENDER_FALLBACK_REQUIRES_CONFIRMATION" if "fallback" in str(error).lower() or "xác nhận" in str(error).lower() else "RENDER_VERIFICATION_FAILED"
        raise api_error(status.HTTP_400_BAD_REQUEST, str(error), code) from error


@router.post("/tikz", dependencies=[Depends(require_trusted_origin)])
async def export_tikz(
    request: SceneRenderRequest,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> Response:
    await enforce_rate_limit(db, http_request, user, "export_tikz", 30 if user else 8, 60)
    await enforce_render_access(db, user)
    from app.renderers.tikz_export import build_tikz_document

    scene = await asyncio.to_thread(_safe_export_scene, request)
    body = await asyncio.to_thread(build_tikz_document, scene, None, request.response)
    return Response(
        content=body,
        media_type="application/x-tex",
        headers={"Content-Disposition": 'attachment; filename="math-renderer.tex"'},
    )


@router.post("/ggb", dependencies=[Depends(require_trusted_origin)])
async def export_ggb(
    request: SceneRenderRequest,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> Response:
    await enforce_rate_limit(db, http_request, user, "export_ggb", 30 if user else 8, 60)
    await enforce_render_access(db, user)
    from app.renderers.ggb_export import build_ggb

    scene = await asyncio.to_thread(_safe_export_scene, request)
    body = await asyncio.to_thread(build_ggb, scene, request.advanced_settings, request.response)
    return Response(
        content=body,
        media_type="application/vnd.geogebra.file",
        headers={"Content-Disposition": 'attachment; filename="math-renderer.ggb"'},
    )


@router.post("/pdf", dependencies=[Depends(require_trusted_origin)])
async def export_pdf(
    request: SceneRenderRequest,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> Response:
    await enforce_rate_limit(db, http_request, user, "export_pdf", 30 if user else 8, 60)
    await enforce_render_access(db, user)
    from app.renderers.pdf_export import build_pdf, build_pdf_from_capture

    scene = await asyncio.to_thread(_safe_export_scene, request)
    try:
        if request.view_capture:
            body = await asyncio.to_thread(build_pdf_from_capture, scene, request.view_capture, request.response)
        else:
            body = await asyncio.to_thread(build_pdf, scene, None, request.response)
    except ValueError as error:
        from fastapi import status

        from app.services.api_errors import api_error

        raise api_error(status.HTTP_400_BAD_REQUEST, str(error), "EXPORT_VIEW_CAPTURE_INVALID") from error
    return Response(
        content=body,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="math-renderer.pdf"'},
    )


@router.post("/png", dependencies=[Depends(require_trusted_origin)])
async def export_png(
    request: SceneRenderRequest,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> Response:
    await enforce_rate_limit(db, http_request, user, "export_png", 30 if user else 8, 60)
    await enforce_render_access(db, user)
    from app.renderers.pdf_export import build_png

    scene = await asyncio.to_thread(_safe_export_scene, request)
    body = await asyncio.to_thread(build_png, scene, None, request.response)
    return Response(
        content=body,
        media_type="image/png",
        headers={"Content-Disposition": 'attachment; filename="math-renderer.png"'},
    )


@router.post("/jpg", dependencies=[Depends(require_trusted_origin)])
async def export_jpg(
    request: SceneRenderRequest,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> Response:
    await enforce_rate_limit(db, http_request, user, "export_jpg", 30 if user else 8, 60)
    await enforce_render_access(db, user)
    from app.renderers.pdf_export import build_jpg

    scene = await asyncio.to_thread(_safe_export_scene, request)
    body = await asyncio.to_thread(build_jpg, scene, None, request.response)
    return Response(
        content=body,
        media_type="image/jpeg",
        headers={"Content-Disposition": 'attachment; filename="math-renderer.jpg"'},
    )


@router.post("/svg", dependencies=[Depends(require_trusted_origin)])
async def export_svg(
    request: SceneRenderRequest,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> Response:
    await enforce_rate_limit(db, http_request, user, "export_svg", 30 if user else 8, 60)
    await enforce_render_access(db, user)
    from app.renderers.pdf_export import build_svg

    scene = _safe_export_scene(request)
    body = build_svg(scene, response=request.response)
    return Response(
        content=body,
        media_type="image/svg+xml; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="math-renderer.svg"'},
    )


@router.post("/katex-html", dependencies=[Depends(require_trusted_origin)])
async def export_katex_html(
    request: SceneRenderRequest,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> Response:
    await enforce_rate_limit(db, http_request, user, "export_katex_html", 30 if user else 8, 60)
    await enforce_render_access(db, user)
    from app.renderers.katex_html_export import build_katex_html

    scene = _safe_export_scene(request)
    body = build_katex_html(scene, request.response)
    return Response(
        content=body,
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="math-renderer-katex.html"'},
    )
