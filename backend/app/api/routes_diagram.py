"""Routes cho OCR hình vẽ và sinh đề biến thể (Phase 4).

- ``POST /api/diagram/ocr`` : Nhận ảnh hình vẽ → mô tả hình hình học (text).
- ``POST /api/problem/variants`` : Nhận MathScene → sinh N đề bài tương đương.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.deps import enforce_rate_limit, require_active_user, require_trusted_origin
from app.api.routes_ocr import enforce_ocr_access
from app.api.routes_render import enforce_render_access
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.admin import AdminRepository
from app.schemas.scene import (
    DiagramOcrRequest,
    DiagramOcrResponse,
    ProblemVariantsRequest,
    ProblemVariantsResponse,
)
from app.services.api_errors import bad_request_from_error
from app.services.model_registry import resolve_effective_settings
from app.services.ocr import extract_text_from_image
from app.services.problem_variants import generate_variants

router = APIRouter(prefix="/api", tags=["diagram"])


@router.post(
    "/diagram/ocr",
    response_model=DiagramOcrResponse,
    dependencies=[Depends(require_trusted_origin)],
)
async def diagram_ocr(
    request: DiagramOcrRequest,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> DiagramOcrResponse:
    await enforce_rate_limit(db, http_request, user, "diagram_ocr", 12 if user else 4, 60)
    await enforce_ocr_access(db, user)
    settings = await resolve_effective_settings(db, request.runtime_settings)
    try:
        result = await extract_text_from_image(
            request.image_data_url,
            settings,
            model=request.preferred_ai_model,
            mode="diagram",
        )
    except (RuntimeError, ValueError) as error:
        raise bad_request_from_error(error, "diagram_ocr_failed") from error
    await AdminRepository(db).record_user_usage_event(user.id, "ocr", {"source": "diagram_ocr", "provider": result.provider, "model": result.model})
    return DiagramOcrResponse(
        description=result.text,
        provider=result.provider,
        model=result.model,
    )


@router.post(
    "/problem/variants",
    response_model=ProblemVariantsResponse,
    dependencies=[Depends(require_trusted_origin)],
)
async def problem_variants(
    request: ProblemVariantsRequest,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> ProblemVariantsResponse:
    await enforce_rate_limit(db, http_request, user, "problem_variants", 18 if user else 4, 60)
    await enforce_render_access(db, user)
    settings = await resolve_effective_settings(db, request.runtime_settings)
    try:
        result = await generate_variants(
            request.scene,
            settings,
            count=request.count,
            original_problem=request.original_problem,
            explicit_model=request.preferred_ai_model,
        )
    except (RuntimeError, ValueError) as error:
        raise bad_request_from_error(error, "problem_variants_failed") from error
    await AdminRepository(db).record_user_usage_event(
        user.id,
        "problem_variants",
        {"count": request.count, "provider": result.provider, "model": result.model},
    )
    return ProblemVariantsResponse(
        variants=result.variants,
        provider=result.provider,
        model=result.model,
    )
