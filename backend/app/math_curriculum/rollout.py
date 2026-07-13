from app.math_curriculum.registry import CAPABILITY_REGISTRY_VERSION

ROLLOUT_VERSION = f"{CAPABILITY_REGISTRY_VERSION}-rollout-v1"


def rollout_stage(status: str) -> str:
    if status == "supported":
        return "public"
    if status == "partial":
        return "internal_beta"
    return "shadow"