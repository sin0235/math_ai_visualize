"""API xuất scene sang TikZ / GGB / PDF.

Body chung: ``SceneRenderRequest`` (đã có) → endpoint trả về file binary/text
tương ứng. Frontend sẽ tải về cho user.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from app.api.deps import enforce_rate_limit, require_active_user, require_trusted_origin
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.schemas.scene import SceneRenderRequest
from app.api.routes_render import enforce_render_access

router = APIRouter(prefix="/api/export", tags=["export"])


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
    from app.services.geometry_engine import normalize_scene

    scene = normalize_scene(request.scene, request.advanced_settings)
    body = build_tikz_document(scene)
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
    from app.services.geometry_engine import normalize_scene

    scene = normalize_scene(request.scene, request.advanced_settings)
    body = build_ggb(scene, request.advanced_settings)
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
    from app.renderers.pdf_export import build_pdf
    from app.services.geometry_engine import normalize_scene

    scene = normalize_scene(request.scene, request.advanced_settings)
    body = build_pdf(scene)
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
    from app.services.geometry_engine import normalize_scene

    scene = normalize_scene(request.scene, request.advanced_settings)
    body = build_png(scene)
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
    from app.services.geometry_engine import normalize_scene

    scene = normalize_scene(request.scene, request.advanced_settings)
    body = build_jpg(scene)
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
    from app.services.geometry_engine import normalize_scene

    scene = normalize_scene(request.scene, request.advanced_settings)
    body = build_svg(scene)
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
    from app.services.geometry_engine import normalize_scene

    scene = normalize_scene(request.scene, request.advanced_settings)
    body = build_katex_html(scene)
    return Response(
        content=body,
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="math-renderer-katex.html"'},
    )
