from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import require_trusted_origin
from app.schemas.algebra import AlgebraSolveRequest, AlgebraSolveResponse
from app.services.algebra import solve_algebra
from app.services.api_errors import api_error

router = APIRouter(prefix="/api/algebra", tags=["algebra"])


@router.post("/solve", response_model=AlgebraSolveResponse, dependencies=[Depends(require_trusted_origin)])
async def solve_algebra_endpoint(request: AlgebraSolveRequest) -> AlgebraSolveResponse:
    try:
        return solve_algebra(request)
    except Exception as error:
        raise api_error(400, f"Lỗi khi giải bài đại số: {error}", "ALGEBRA_SOLVE_FAILED") from error
