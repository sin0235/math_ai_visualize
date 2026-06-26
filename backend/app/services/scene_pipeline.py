from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings
from app.schemas.scene import (
    AdvancedRenderSettings,
    MathScene,
    RenderPayload,
    RenderResponse,
    RenderSourceResponse,
    ValidationItem,
    ValidationReportResponse,
)
from app.services.cas_verifier import build_repair_report, verify_scene, verify_scene_relations
from app.services.geometry_engine import normalize_scene
from app.services.quality_advisory import build_render_advisory, build_scene_advisory
from app.services.renderer_router import build_render_payload, validate_renderer_compatibility
from app.services.scene_validator import validate_and_repair


@dataclass(frozen=True)
class ScenePipelineResult:
    response: RenderResponse


def validate_normalize_verify_scene(
    scene: MathScene,
    settings: AdvancedRenderSettings,
    *,
    warnings: list[str] | None = None,
    source: RenderSourceResponse | None = None,
    build_problem_advisory: bool = True,
) -> ScenePipelineResult:
    pipeline_warnings = list(warnings or [])
    source = source or RenderSourceResponse(kind="scene_edit")
    scene = _apply_scene_audit(scene, source)
    validation = validate_and_repair(scene)
    scene = validation.scene
    validation_report = _validation_report_from_validator(validation.errors, validation.warnings, validation.repairs)
    pipeline_warnings.extend(validation.all_warnings)

    if settings.verify_scene:
        verification_report = verify_scene_relations(scene)
        repair_report = build_repair_report(scene, verify_scene(scene))
    else:
        verification_report = verify_scene_relations(scene.model_copy(update={"relations": []}))
        verification_report.status = "partial"
        repair_report = build_repair_report(scene, [])
        pipeline_warnings.append("[CAS] Đã tắt kiểm chứng quan hệ hình học để dựng hình nhanh hơn.")
    if repair_report.requires_confirmation:
        pipeline_warnings.extend(repair_report.warnings)

    scene = _attach_relation_verification(scene, verification_report)
    scene = normalize_scene(scene, settings)
    compatibility = validate_renderer_compatibility(scene)
    payload: RenderPayload
    if compatibility.status == "incompatible":
        payload = RenderPayload(renderer=scene.renderer)
        status = "failed"
        requires_confirmation = True
        pipeline_warnings.extend(compatibility.messages)
    else:
        payload = build_render_payload(scene, settings)
        status = _status_from_reports(validation_report.status, verification_report.status, source, repair_report.requires_confirmation)
        requires_confirmation = status in {"failed", "fallback", "needs_confirmation", "partially_verified"} or repair_report.requires_confirmation

    advisory = None
    if get_settings().advisory_enabled:
        if build_problem_advisory:
            advisory = build_render_advisory(scene.problem_text, scene.grade, scene, pipeline_warnings, scene.cas_issues, payload)
        else:
            advisory = build_scene_advisory(scene, pipeline_warnings, payload)

    response = RenderResponse(
        status=status,
        source=source,
        scene=scene,
        payload=payload,
        warnings=pipeline_warnings,
        validation_report=validation_report,
        verification_report=verification_report,
        repair_report=repair_report,
        renderer_compatibility=compatibility,
        requires_user_confirmation=requires_confirmation,
        cas_issues=scene.cas_issues,
        advisory=advisory,
        degraded=bool(source and source.fallback_used),
        fallback_source="mock" if source and source.kind == "mock" else "provider_fallback" if source and source.fallback_used else "none",
        ai_source="none" if source and source.kind in {"scene_edit", "manual", "none"} else "byok" if source and source.kind == "byok" else "admin",
    )
    return ScenePipelineResult(response=response)



def _apply_scene_audit(scene: MathScene, source: RenderSourceResponse) -> MathScene:
    data = scene.model_dump()
    audit = data.get("audit") if isinstance(data.get("audit"), dict) else {}
    audit["created_by"] = source.kind
    audit["generator_provider"] = source.provider
    audit["generator_model"] = source.model
    data["audit"] = audit
    return MathScene.model_validate(data)

def _validation_report_from_validator(errors: list[str], warnings: list[str], repairs: list[str]) -> ValidationReportResponse:
    items: list[ValidationItem] = []
    items.extend(ValidationItem(code="validator_error", severity="error", message=message) for message in errors)
    items.extend(ValidationItem(code="validator_warning", severity="warning", message=message) for message in warnings)
    items.extend(ValidationItem(code="validator_repair", severity="info", message=message) for message in repairs)
    status = "failed" if errors else "partial" if warnings or repairs else "passed"
    return ValidationReportResponse(status=status, items=items)


def _attach_relation_verification(scene: MathScene, verification_report) -> MathScene:
    by_id = {item.relation_id: item for item in verification_report.relations}
    data = scene.model_dump()
    for rel in data.get("relations", []):
        rel_id = rel.get("id")
        if rel_id in by_id:
            rel["verification"] = by_id[rel_id].model_dump(mode="json")
    return MathScene.model_validate(data)


def _status_from_reports(validation_status: str, verification_status: str, source: RenderSourceResponse | None, repair_requires_confirmation: bool = False):
    if validation_status == "failed":
        return "failed"
    if source and source.kind == "mock":
        return "fallback"
    if source and source.fallback_used:
        return "needs_confirmation"
    if repair_requires_confirmation:
        return "needs_confirmation"
    if verification_status == "passed":
        return "verified"
    if verification_status == "failed":
        return "partially_verified"
    return "partially_verified"
