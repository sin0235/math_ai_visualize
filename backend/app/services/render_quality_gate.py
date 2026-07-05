from __future__ import annotations

from app.schemas.scene import MathScene, RelationVerificationResponse, RenderResponse
from app.services.cas_verifier import verify_scene, verify_scene_relations
from app.services.scene_trust import assert_no_unconfirmed_scene_assumptions

_UNSAFE_VERIFICATION_STATUSES = {"failed", "error"}
_PARTIAL_VERIFICATION_STATUSES = {"unsupported", "unverifiable"}


def assert_render_response_safe_for_downstream(
    response: RenderResponse,
    scene: MathScene,
    *,
    operation: str,
    allow_partial: bool = False,
) -> None:
    """Kiểm tra response v2 và scene đang thao tác cùng một trust boundary."""
    if response.status == "failed":
        raise ValueError(f"Scene dựng hình thất bại nên chưa thể {operation}.")
    needs_confirmation = (
        response.status in {"fallback", "needs_confirmation"}
        or response.requires_user_confirmation
        or response.source.fallback_used
    )
    if needs_confirmation and not response.user_confirmed:
        raise ValueError(f"Scene chưa đủ tin cậy để {operation}; hãy xác nhận hoặc dựng lại hình trước.")
    _assert_same_scene_revision(response.scene, scene)
    assert_scene_safe_for_downstream(
        scene,
        operation=operation,
        allow_partial=allow_partial,
        user_confirmed=response.user_confirmed,
    )


def assert_scene_safe_for_downstream(
    scene: MathScene,
    *,
    operation: str,
    allow_partial: bool = False,
    user_confirmed: bool = False,
) -> None:
    """Chặn solver/variants/export dùng scene chưa đạt ngưỡng tin cậy tối thiểu."""
    created_by = scene.audit.created_by if scene.audit else "none"
    assert_no_unconfirmed_scene_assumptions(scene, operation=operation, user_confirmed=user_confirmed)
    if created_by == "mock" and not user_confirmed:
        raise ValueError(f"Scene fallback/mock cần được người dùng xác nhận trước khi {operation}.")

    verifications = _relation_verifications(scene)
    unsafe = [item for item in verifications if item.status in _UNSAFE_VERIFICATION_STATUSES]
    if unsafe:
        relation_ids = ", ".join(item.relation_id for item in unsafe[:5])
        raise ValueError(f"Scene có quan hệ kiểm chứng thất bại nên không thể {operation}: {relation_ids}.")

    if not allow_partial:
        partial = [item for item in verifications if item.status in _PARTIAL_VERIFICATION_STATUSES]
        if partial:
            relation_ids = ", ".join(item.relation_id for item in partial[:5])
            raise ValueError(f"Scene còn quan hệ chưa kiểm chứng đầy đủ nên không thể {operation}: {relation_ids}.")

    cas_issues = verify_scene(scene)
    blocking_issues = [
        issue for issue in cas_issues
        if issue.severity == "error" or (not allow_partial and not issue.auto_fixed)
    ]
    if blocking_issues:
        descriptions = "; ".join(issue.description for issue in blocking_issues[:3])
        raise ValueError(f"Scene còn vấn đề CAS nên không thể {operation}: {descriptions}.")


def _assert_same_scene_revision(response_scene: MathScene, scene: MathScene) -> None:
    if response_scene.scene_id and scene.scene_id and response_scene.scene_id != scene.scene_id:
        raise ValueError("Scene hiện tại không khớp render response đã được kiểm chứng; hãy dựng lại hình trước.")
    if response_scene.revision != scene.revision:
        raise ValueError("Revision scene hiện tại không khớp render response đã được kiểm chứng; hãy dựng lại hình trước.")


def _relation_verifications(scene: MathScene) -> list[RelationVerificationResponse]:
    return verify_scene_relations(scene).relations
