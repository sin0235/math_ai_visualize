from __future__ import annotations

from typing import Iterable

from app.schemas.scene import Annotation, MathScene, RenderResponse


_MEASUREMENT_ANNOTATIONS = {"length", "angle", "coordinate_label"}
_RELATION_MARK_ANNOTATIONS = {"right_angle", "equal_marks"}
_TRUSTED_MEASUREMENT_SOURCES = {"given", "user_created", "user_edited"}
_TRUSTED_RELATION_SOURCES = {"given", "inferred", "verified", "user_created", "user_edited"}


def scene_assumption_items(scene: MathScene) -> list[str]:
    interpretation = scene.interpretation
    if not interpretation:
        return []
    items = [*interpretation.assumptions]
    items.extend(f"Thiếu dữ kiện: {item}" for item in interpretation.missing_data)
    return [item.strip() for item in items if item and item.strip()]


def assert_no_unconfirmed_scene_assumptions(scene: MathScene, *, operation: str, user_confirmed: bool = False) -> None:
    items = scene_assumption_items(scene)
    if items and not user_confirmed:
        raise ValueError(f"Scene có giả định hoặc thiếu dữ kiện chưa được xác nhận nên chưa thể {operation}.")


def is_exact_construction(scene: MathScene, response: RenderResponse | None = None) -> bool:
    if scene_assumption_items(scene):
        return False
    if scene.audit and scene.audit.created_by == "mock":
        return False
    if response is None:
        return False
    return (
        response.status == "verified"
        and response.verification_report.status == "passed"
        and response.renderer_compatibility.status == "compatible"
        and not response.requires_user_confirmation
        and not response.source.fallback_used
        and not response.degraded
        and response.fallback_source in {None, "none"}
    )


def scene_trust_labels(scene: MathScene, response: RenderResponse | None = None) -> list[str]:
    exact = is_exact_construction(scene, response)
    labels = ["Dựng theo dữ kiện" if exact else "Hình minh họa"]
    if not exact:
        labels.append("Không theo tỉ lệ")
    if scene_assumption_items(scene):
        labels.append("Có giả định")
    return labels


def export_notice_lines(scene: MathScene, response: RenderResponse | None = None, hidden_annotations: int = 0) -> list[str]:
    labels = scene_trust_labels(scene, response)
    lines = [" · ".join(labels)]
    if "Hình minh họa" in labels:
        lines.append("Không dùng hình minh họa để suy ra quan hệ hoặc kết luận số học.")
    assumptions = scene_assumption_items(scene)
    if assumptions:
        lines.append("Giả định/dữ kiện thiếu: " + "; ".join(assumptions[:3]))
    if hidden_annotations:
        lines.append(f"Đã ẩn {hidden_annotations} nhãn đo/quan hệ không có nguồn dữ kiện tin cậy.")
    return lines


def annotation_is_trusted_for_display(annotation: Annotation) -> bool:
    source = _annotation_source(annotation)
    confidence = str(annotation.metadata.get("confidence") or "").strip().lower()
    if confidence == "unverified" or source == "construction":
        return False
    if annotation.type in _MEASUREMENT_ANNOTATIONS:
        return source in _TRUSTED_MEASUREMENT_SOURCES
    if annotation.type in _RELATION_MARK_ANNOTATIONS:
        return source in _TRUSTED_RELATION_SOURCES
    return source in _TRUSTED_MEASUREMENT_SOURCES or source in _TRUSTED_RELATION_SOURCES


def trusted_display_annotations(annotations: Iterable[Annotation]) -> list[Annotation]:
    return [annotation for annotation in annotations if annotation_is_trusted_for_display(annotation)]


def scene_with_trusted_annotations(scene: MathScene) -> tuple[MathScene, int]:
    annotations = trusted_display_annotations(scene.annotations)
    hidden = len(scene.annotations) - len(annotations)
    if hidden <= 0:
        return scene, 0
    return scene.model_copy(update={"annotations": annotations}), hidden


def _annotation_source(annotation: Annotation) -> str:
    raw = annotation.metadata.get("source") or annotation.source
    return str(raw or "").strip().lower()