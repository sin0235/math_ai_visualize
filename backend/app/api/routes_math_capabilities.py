from fastapi import APIRouter

from app.schemas.math_capabilities import MathCapabilityRegistry
from app.services.math_capabilities import math_capability_registry


router = APIRouter(prefix="/api/math", tags=["math-capabilities"])


@router.get("/capabilities", response_model=MathCapabilityRegistry)
def get_math_capabilities() -> MathCapabilityRegistry:
    return math_capability_registry()