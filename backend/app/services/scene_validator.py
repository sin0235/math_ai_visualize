"""LLM Response Validator + Auto-Repair cho MathScene.

Pydantic chỉ check kiểu dữ liệu (structural) — chưa đủ để bắt LLM trả về
scene "đúng schema" nhưng SAI Ý NGHĨA:

- Segment tham chiếu điểm "K" trong khi không có point K trong objects.
- Hai object cùng tên "A".
- renderer = "geogebra_2d" nhưng có vài point_3d.
- Sphere có radius <= 0.
- *_expr dùng biến "k" nhưng parameter "k" không khai báo.
- Parameter có default nằm ngoài [min, max].
- Annotation "right_angle" target = "ABC" thay vì 1 đỉnh.

Module này chạy SAU Pydantic, TRƯỚC CAS verifier:

    raw JSON → normalize → Pydantic → scene_validator → cas_verifier

Trả về `ValidationReport` gồm:
- scene: scene đã auto-repair (tốt nhất có thể)
- errors: vi phạm nghiêm trọng đã phải drop object/relation
- warnings: vi phạm nhẹ đã sửa hoặc cần lưu ý
- repairs: các thao tác sửa đã thực hiện (để debug)

Triết lý: ưu tiên SCENE RENDER ĐƯỢC. Thà drop 1 segment lỗi còn hơn để
toàn bộ render fail. Mọi quyết định drop/sửa đều log warning rõ ràng.
"""

from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass, field

from app.schemas.scene import (
    MathScene,
    Point2D,
    Point3D,
)
from app.services.expression_eval import _ALLOWED_CONSTS, _ALLOWED_FUNCS
from app.services.linalg import bbox_diagonal, cross, distance, norm, plane_from_points, sub, vec3


@dataclass
class ValidationReport:
    """Kết quả validate + auto-repair."""

    scene: MathScene
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    repairs: list[str] = field(default_factory=list)

    @property
    def all_warnings(self) -> list[str]:
        """Các warning hiển thị cho user (gộp errors + warnings + repairs)."""
        out: list[str] = []
        for msg in self.errors:
            out.append(f"[Validator] Lỗi: {msg}")
        for msg in self.repairs:
            out.append(f"[Validator] Đã sửa: {msg}")
        for msg in self.warnings:
            out.append(f"[Validator] Cảnh báo: {msg}")
        return out


# ---------------------------------------------------------------------------
# Pre-Pydantic guard: clean rõ rệt một số lỗi LLM hay sinh ngay trên dict
# (trước khi gọi MathScene.model_validate).
# ---------------------------------------------------------------------------


_VALID_OBJECT_TYPES = {
    "point_2d", "point_3d", "segment", "line_2d", "line_3d",
    "vector_2d", "vector_3d", "circle_2d", "function_graph",
    "face", "sphere", "plane",
}

_VALID_RELATION_TYPES = {
    "perpendicular", "parallel", "equal_length", "midpoint",
    "intersection", "tangent", "collinear", "coplanar",
    "on_line", "on_plane", "on_sphere", "on_circle",
    "distance", "angle",
}

_VALID_ANNOTATION_TYPES = {
    "length", "angle", "right_angle", "equal_marks", "coordinate_label",
}
_VALID_FACT_SOURCES = {"given", "inferred", "construction"}
_VALID_FACT_CONFIDENCE = {"verified", "partial", "unverified"}


def pre_validate_raw(scene_json: dict) -> tuple[dict, list[str]]:
    """Chuẩn hoá dict JSON từ LLM trước khi đưa vào Pydantic.

    Drop các object/relation/annotation có type không hợp lệ thay vì để
    Pydantic raise ValidationError tổng. Trả về (dict đã clean, warnings).
    """
    warnings: list[str] = []
    if not isinstance(scene_json, dict):
        return {}, ["Scene JSON không phải object"]

    data = dict(scene_json)

    # Lọc objects
    raw_objects = data.get("objects")
    if isinstance(raw_objects, list):
        cleaned: list[dict] = []
        for idx, obj in enumerate(raw_objects):
            if not isinstance(obj, dict):
                warnings.append(f"objects[{idx}] không phải dict — đã bỏ")
                continue
            otype = obj.get("type")
            if otype not in _VALID_OBJECT_TYPES:
                warnings.append(f"objects[{idx}] có type='{otype}' không hợp lệ — đã bỏ")
                continue
            cleaned.append(obj)
        data["objects"] = cleaned

    # Lọc relations
    raw_relations = data.get("relations")
    if isinstance(raw_relations, list):
        cleaned_rels: list[dict] = []
        for idx, rel in enumerate(raw_relations):
            if not isinstance(rel, dict):
                warnings.append(f"relations[{idx}] không phải dict — đã bỏ")
                continue
            rtype = (rel.get("type") or "").strip().lower()
            if rtype not in _VALID_RELATION_TYPES:
                warnings.append(f"relations[{idx}] type='{rel.get('type')}' không hợp lệ — đã bỏ")
                continue
            rel["type"] = rtype
            cleaned_rels.append(rel)
        data["relations"] = cleaned_rels

    # Lọc annotations
    raw_anns = data.get("annotations")
    if isinstance(raw_anns, list):
        cleaned_anns: list[dict] = []
        for idx, ann in enumerate(raw_anns):
            if not isinstance(ann, dict):
                warnings.append(f"annotations[{idx}] không phải dict — đã bỏ")
                continue
            atype = ann.get("type")
            if atype not in _VALID_ANNOTATION_TYPES:
                warnings.append(f"annotations[{idx}] type='{atype}' không hợp lệ — đã bỏ")
                continue
            cleaned_anns.append(ann)
        data["annotations"] = cleaned_anns

    return data, warnings


# ---------------------------------------------------------------------------
# Post-Pydantic semantic validator
# ---------------------------------------------------------------------------


_EXPR_NAME_RE = re.compile(r"\b([A-Za-z_]\w*)\b")
_RESERVED_NAMES: set[str] = set(_ALLOWED_FUNCS) | set(_ALLOWED_CONSTS)


def validate_and_repair(scene: MathScene) -> ValidationReport:
    """Kiểm tra ngữ nghĩa scene + auto-repair các lỗi phổ biến.

    Các bước:
      1. Naming uniqueness — drop trùng tên (giữ object đầu tiên).
      2. Annotation shape — chuẩn hoá target/arms (chạy trước reference
         integrity để tách 'ABC' → target='B', arms=['A','C']).
      3. Reference integrity — drop các object/relation/annotation tham
         chiếu điểm không tồn tại.
      4. Dimension consistency — cảnh báo nếu renderer ≠ kiểu point.
      5. Geometry sanity — radius/segment/face/plane.
      6. Parameter integrity — clamp default, drop _expr lỗi.
    """
    report = ValidationReport(scene=scene)

    # 1. Naming uniqueness
    scene = _dedupe_names(scene, report)

    # 2. Annotation shape (trước reference check để 'ABC' → 'B'+arms)
    scene = _normalize_annotations(scene, report)

    # 3. Reference integrity
    scene = _enforce_references(scene, report)

    # 4. Dimension consistency
    _check_dimension_consistency(scene, report)

    # 5. Geometry sanity
    scene = _enforce_geometry_sanity(scene, report)

    # 6. Parameter integrity
    scene = _enforce_parameters(scene, report)

    # 7. Fact metadata
    scene = _normalize_fact_metadata(scene, report)

    # 8. Numeric quality warnings
    _check_numeric_quality(scene, report)

    report.scene = scene
    return report


def _normalize_fact_metadata(scene: MathScene, report: ValidationReport) -> MathScene:
    data = scene.model_dump()
    changed = False

    for rel in data.get("relations", []):
        if not isinstance(rel, dict):
            continue
        metadata = rel.get("metadata") if isinstance(rel.get("metadata"), dict) else {}
        new_metadata, did_change = _normalized_metadata(
            metadata,
            default_source="inferred",
            default_confidence="partial",
        )
        if did_change:
            rel["metadata"] = new_metadata
            changed = True

    for ann in data.get("annotations", []):
        if not isinstance(ann, dict):
            continue
        metadata = ann.get("metadata") if isinstance(ann.get("metadata"), dict) else {}
        default_source, default_confidence = _annotation_metadata_defaults(ann)
        new_metadata, did_change = _normalized_metadata(
            metadata,
            default_source=default_source,
            default_confidence=default_confidence,
        )
        if did_change:
            ann["metadata"] = new_metadata
            changed = True

    if changed:
        report.repairs.append("Đã chuẩn hoá metadata nguồn/độ tin cậy cho dữ kiện hình học")
        return MathScene.model_validate(data)
    return scene


def _annotation_metadata_defaults(annotation: dict) -> tuple[str, str]:
    atype = annotation.get("type")
    label = annotation.get("label")
    if atype in {"length", "angle"} and isinstance(label, str) and label.strip():
        return "given", "partial"
    if atype in {"right_angle", "equal_marks"}:
        return "inferred", "partial"
    return "construction", "unverified"


def _normalized_metadata(
    metadata: dict,
    *,
    default_source: str,
    default_confidence: str,
) -> tuple[dict, bool]:
    normalized = dict(metadata)
    source = normalized.get("source")
    confidence = normalized.get("confidence")
    evidence = normalized.get("evidence")
    changed = False

    if source not in _VALID_FACT_SOURCES:
        normalized["source"] = default_source
        changed = True
    if confidence not in _VALID_FACT_CONFIDENCE:
        normalized["confidence"] = default_confidence
        changed = True
    if evidence is not None and not isinstance(evidence, str):
        normalized["evidence"] = str(evidence)
        changed = True
    return normalized, changed


# ---------------------------------------------------------------------------
# 1. Naming uniqueness
# ---------------------------------------------------------------------------


def _dedupe_names(scene: MathScene, report: ValidationReport) -> MathScene:
    seen: set[str] = set()
    new_objects = []
    for obj in scene.objects:
        name = getattr(obj, "name", None)
        if name and isinstance(name, str):
            if name in seen:
                report.repairs.append(
                    f"Object '{name}' (type={obj.type}) trùng tên với object trước — đã bỏ"
                )
                continue
            seen.add(name)
        new_objects.append(obj)
    if len(new_objects) != len(scene.objects):
        data = scene.model_dump()
        data["objects"] = [o.model_dump() for o in new_objects]
        return MathScene.model_validate(data)
    return scene


# ---------------------------------------------------------------------------
# 2. Reference integrity
# ---------------------------------------------------------------------------


def _collect_point_names(scene: MathScene) -> set[str]:
    return {obj.name for obj in scene.objects if isinstance(obj, (Point2D, Point3D))}


def _collect_named_objects(scene: MathScene) -> dict[str, str]:
    """Map name → type cho mọi object có tên (để check tham chiếu trong relation)."""
    out: dict[str, str] = {}
    for obj in scene.objects:
        name = getattr(obj, "name", None)
        if isinstance(name, str) and name:
            out[name] = obj.type
    return out


def _segment_token_points(token: str) -> list[str]:
    """Trích danh sách tên điểm từ chuỗi 'A-B', 'AB', 'plane(ABC)', 'A,B,C'."""
    if not token:
        return []
    token = token.strip()
    if token.startswith("plane(") and token.endswith(")"):
        inside = token[6:-1]
        return [c for c in inside if c.isupper()]
    if token.startswith("(") and token.endswith(")"):
        inside = token[1:-1]
        return [c for c in inside if c.isupper()]
    if "-" in token:
        return [p.strip() for p in token.split("-") if p.strip()]
    if "," in token:
        return [p.strip() for p in token.split(",") if p.strip()]
    if len(token) >= 2 and all(c.isupper() for c in token):
        return list(token)
    return [token] if token.isidentifier() else []


def _enforce_references(scene: MathScene, report: ValidationReport) -> MathScene:
    points = _collect_point_names(scene)
    named_objects = _collect_named_objects(scene)
    data = scene.model_dump()
    changed = False

    # Objects
    new_objects: list[dict] = []
    for obj in data.get("objects", []):
        otype = obj.get("type")
        bad: list[str] = []

        if otype == "segment":
            for p in obj.get("points", []) or []:
                if p not in points:
                    bad.append(p)
            if len(set(obj.get("points", []) or [])) < 2:
                bad.append("points trùng")
        elif otype in {"line_2d", "line_3d"}:
            for p in obj.get("through", []) or []:
                if p not in points:
                    bad.append(p)
        elif otype in {"vector_2d", "vector_3d"}:
            for key in ("from_point", "to_point"):
                p = obj.get(key)
                if p and p not in points:
                    bad.append(p)
        elif otype == "circle_2d":
            center = obj.get("center")
            if center and center not in points:
                bad.append(center)
            through = obj.get("through")
            if through and through not in points:
                bad.append(through)
        elif otype in {"face", "plane"}:
            for p in obj.get("points", []) or []:
                if p not in points:
                    bad.append(p)
        elif otype == "sphere":
            center = obj.get("center")
            if center and center not in points:
                bad.append(center)

        if bad:
            label = obj.get("name") or otype
            report.repairs.append(
                f"Object '{label}' tham chiếu điểm không tồn tại: {sorted(set(bad))} — đã bỏ"
            )
            changed = True
            continue
        new_objects.append(obj)
    data["objects"] = new_objects

    # Relations
    new_relations: list[dict] = []
    for rel in data.get("relations", []):
        rtype = rel.get("type")
        tokens = [rel.get("object_1") or "", rel.get("object_2") or ""]
        missing: list[str] = []
        for token in tokens:
            for ref in _segment_token_points(token):
                if ref and ref not in points and ref not in named_objects:
                    missing.append(ref)
        if missing:
            report.warnings.append(
                f"Relation '{rtype}' tham chiếu '{','.join(sorted(set(missing)))}' không tồn tại — đã bỏ"
            )
            changed = True
            continue
        new_relations.append(rel)
    data["relations"] = new_relations

    # Annotations
    new_anns: list[dict] = []
    for ann in data.get("annotations", []):
        atype = ann.get("type")
        target = ann.get("target") or ""
        meta = ann.get("metadata") or {}
        ref_ok = True
        missing_pts: list[str] = []
        if atype in {"length", "equal_marks"}:
            for p in _segment_token_points(target):
                if p and p not in points:
                    missing_pts.append(p)
                    ref_ok = False
        elif atype in {"right_angle", "angle", "coordinate_label"}:
            if target and target not in points:
                missing_pts.append(target)
                ref_ok = False
            arms = meta.get("arms") if isinstance(meta, dict) else None
            if isinstance(arms, list):
                for a in arms:
                    if isinstance(a, str) and a and a not in points:
                        missing_pts.append(a)
                        ref_ok = False

        if not ref_ok:
            report.warnings.append(
                f"Annotation '{atype}' tham chiếu '{','.join(sorted(set(missing_pts)))}' không tồn tại — đã bỏ"
            )
            changed = True
            continue
        new_anns.append(ann)
    data["annotations"] = new_anns

    if changed:
        return MathScene.model_validate(data)
    return scene


# ---------------------------------------------------------------------------
# 3. Dimension consistency
# ---------------------------------------------------------------------------


def _check_dimension_consistency(scene: MathScene, report: ValidationReport) -> None:
    """Cảnh báo nếu renderer 2D có Point3D hoặc renderer 3D có Point2D."""
    point_2d_count = sum(1 for o in scene.objects if isinstance(o, Point2D))
    point_3d_count = sum(1 for o in scene.objects if isinstance(o, Point3D))
    renderer = scene.renderer

    if renderer == "geogebra_2d" and point_3d_count > 0:
        report.warnings.append(
            f"renderer='geogebra_2d' nhưng có {point_3d_count} point_3d — frontend có thể render sai"
        )
    if renderer == "threejs_3d" and point_2d_count > 0:
        report.warnings.append(
            f"renderer='threejs_3d' nhưng có {point_2d_count} point_2d — frontend có thể render sai"
        )

    view_dim = scene.view.dimension
    if view_dim == "2d" and point_3d_count > 0:
        report.warnings.append(
            f"view.dimension='2d' nhưng có {point_3d_count} point_3d — không nhất quán"
        )
    if view_dim == "3d" and point_2d_count > 0 and renderer != "geogebra_2d":
        report.warnings.append(
            f"view.dimension='3d' nhưng có {point_2d_count} point_2d — không nhất quán"
        )


# ---------------------------------------------------------------------------
# 4. Geometry sanity
# ---------------------------------------------------------------------------


def _enforce_geometry_sanity(scene: MathScene, report: ValidationReport) -> MathScene:
    points: dict[str, Point2D | Point3D] = {
        obj.name: obj for obj in scene.objects if isinstance(obj, (Point2D, Point3D))
    }
    data = scene.model_dump()
    changed = False
    new_objects: list[dict] = []
    for obj in data.get("objects", []):
        otype = obj.get("type")
        keep = True

        if otype == "segment":
            pts = obj.get("points", []) or []
            if len(pts) >= 2 and pts[0] == pts[1]:
                report.repairs.append(
                    f"Segment '{obj.get('name') or pts[0]+pts[1]}' có 2 điểm trùng nhau — đã bỏ"
                )
                keep = False
        elif otype == "circle_2d":
            radius = obj.get("radius")
            if radius is None and not obj.get("through"):
                report.repairs.append(
                    f"Circle '{obj.get('name') or '?'}' thiếu radius và through — đã bỏ"
                )
                keep = False
            elif isinstance(radius, (int, float)) and radius <= 0:
                # Nếu có through thì có thể tự suy radius — giữ lại, render fallback
                if obj.get("through"):
                    obj["radius"] = None
                    report.repairs.append(
                        f"Circle '{obj.get('name') or '?'}' radius<=0 — đã chuyển sang dùng through"
                    )
                else:
                    report.repairs.append(
                        f"Circle '{obj.get('name') or '?'}' radius={radius} không hợp lệ — đã bỏ"
                    )
                    keep = False
        elif otype == "sphere":
            radius = obj.get("radius")
            if not isinstance(radius, (int, float)) or radius <= 0:
                report.repairs.append(
                    f"Sphere '{obj.get('name') or '?'}' radius={radius} không hợp lệ — đã bỏ"
                )
                keep = False
        elif otype in {"face", "plane"}:
            pts = obj.get("points", []) or []
            unique_pts = list(dict.fromkeys(pts))
            if len(unique_pts) < 3:
                report.repairs.append(
                    f"{otype} '{obj.get('name') or ''}' chỉ có {len(unique_pts)} điểm phân biệt — đã bỏ"
                )
                keep = False
            elif len(unique_pts) != len(pts):
                obj["points"] = unique_pts
                report.repairs.append(
                    f"{otype} '{obj.get('name') or ''}' có điểm lặp — đã rút gọn còn {len(unique_pts)}"
                )
            # Cảnh báo (không drop) nếu các điểm thẳng hàng
            if keep and otype == "face" and len(unique_pts) >= 3:
                if _are_collinear([points[n] for n in unique_pts if n in points]):
                    report.warnings.append(
                        f"face '{obj.get('name') or ''}' có các điểm thẳng hàng — diện tích = 0"
                    )
        elif otype in {"line_2d", "line_3d"}:
            pts = obj.get("through", []) or []
            if len(pts) >= 2 and pts[0] == pts[1]:
                report.repairs.append(
                    f"line '{obj.get('name') or ''}' có 2 điểm trùng — đã bỏ"
                )
                keep = False
        elif otype in {"vector_2d", "vector_3d"}:
            if obj.get("from_point") == obj.get("to_point"):
                report.repairs.append(
                    f"vector '{obj.get('name') or ''}' có from=to — đã bỏ (vector 0)"
                )
                keep = False
        elif otype == "function_graph":
            expr = obj.get("expression")
            if not isinstance(expr, str) or not expr.strip():
                report.repairs.append(
                    f"function_graph '{obj.get('name') or '?'}' thiếu expression — đã bỏ"
                )
                keep = False
            else:
                normalized_expr = _normalize_function_expression(expr)
                if normalized_expr != expr:
                    obj["expression"] = normalized_expr
                    changed = True
                    report.repairs.append(
                        f"function_graph '{obj.get('name') or '?'}' expression LaTeX — đã chuẩn hoá"
                    )

        if not keep:
            changed = True
            continue
        new_objects.append(obj)

    if changed:
        data["objects"] = new_objects
        return MathScene.model_validate(data)
    return scene


def _normalize_function_expression(expression: str) -> str:
    expr = expression.strip()
    expr = re.sub(r"^\\\\\((.*)\\\\\)$", r"\1", expr)
    expr = re.sub(r"^\\\\\[(.*)\\\\\]$", r"\1", expr)
    expr = expr.strip("$ ")
    expr = re.sub(r"^y\s*=\s*", "", expr, flags=re.IGNORECASE)
    expr = re.sub(r"\\\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}", r"(\1)/(\2)", expr)
    expr = expr.replace("\\\\cdot", "*").replace("\\\\times", "*")
    expr = expr.replace("\\\\left", "").replace("\\\\right", "")
    expr = expr.replace("{", "(").replace("}", ")")
    expr = expr.replace(" ", "")
    expr = re.sub(r"(?<=\d)(?=[A-Za-z])", "*", expr)
    expr = re.sub(r"(?<=\))(?=[A-Za-z0-9(])", "*", expr)
    expr = re.sub(r"(?<=[A-Za-z])(?=\()", "*", expr)
    return expr


def _are_collinear(pts: list[Point2D | Point3D]) -> bool:
    if len(pts) < 3:
        return False
    p0 = pts[0]
    if isinstance(p0, Point3D):
        coords = [(p.x, p.y, p.z) for p in pts if isinstance(p, Point3D)]
    else:
        coords = [(p.x, p.y, 0.0) for p in pts if isinstance(p, Point2D)]
    if len(coords) < 3:
        return False
    p0c = vec3(*coords[0])
    base = sub(vec3(*coords[1]), p0c)
    base_len = norm(base)
    if base_len < 1e-9:
        return True
    for c in coords[2:]:
        v = sub(vec3(*c), p0c)
        cross_value = cross(base, v)
        cn = norm(cross_value)
        v_len = norm(v)
        if cn > 1e-9 * max(base_len * v_len, 1.0):
            return False
    return True


# ---------------------------------------------------------------------------
# 5. Numeric quality warnings
# ---------------------------------------------------------------------------


def _check_numeric_quality(scene: MathScene, report: ValidationReport) -> None:
    points3d = {obj.name: vec3(obj.x, obj.y, obj.z) for obj in scene.objects if isinstance(obj, Point3D)}
    names = list(points3d)
    for i, first in enumerate(names):
        for second in names[i + 1:]:
            if distance(points3d[first], points3d[second]) <= 1e-7:
                report.warnings.append(f"Điểm {first} và {second} gần trùng nhau — cấu hình có thể suy biến")

    for obj in scene.objects:
        if obj.type not in {"face", "plane"}:
            continue
        point_names = getattr(obj, "points", [])
        coords = [points3d[name] for name in point_names if name in points3d]
        if len(coords) < 3:
            continue
        try:
            diagonal = bbox_diagonal(coords)
        except ValueError:
            continue
        if diagonal <= 1e-9:
            report.warnings.append(f"{obj.type} '{getattr(obj, 'name', None) or ''.join(point_names)}' gần suy biến vì các điểm quá gần nhau")
            continue
        plane = plane_from_points(coords, 1e-9)
        if plane is None:
            continue
        center, normal = plane
        max_offset = max(abs(float((coord - center).dot(normal))) for coord in coords)
        if max_offset > 1e-6 * max(diagonal, 1.0):
            report.warnings.append(f"{obj.type} '{getattr(obj, 'name', None) or ''.join(point_names)}' không gần đồng phẳng tuyệt đối (lệch {max_offset:.3g})")


# ---------------------------------------------------------------------------
# 6. Parameter integrity
# ---------------------------------------------------------------------------


def _expr_free_names(expr: str) -> set[str]:
    """Trích các tên định danh trong expression, loại function/const đã biết."""
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            if node.id not in _RESERVED_NAMES:
                names.add(node.id)
    return names


def _enforce_parameters(scene: MathScene, report: ValidationReport) -> MathScene:
    """Ràng buộc parameters và *_expr.

    - Param.default phải nằm trong [min, max].
    - Param.min < Param.max.
    - *_expr phải parse được, mọi biến phải có trong parameters.
    - Nếu *_expr lỗi → clear, giữ giá trị x/y/z float hiện có.
    """
    data = scene.model_dump()
    changed = False

    # Validate parameters list
    params = data.get("parameters") or []
    new_params: list[dict] = []
    param_names: set[str] = set()
    for p in params:
        name = p.get("name")
        if not isinstance(name, str) or not name.strip() or not name.isidentifier():
            report.repairs.append(f"Parameter '{name}' tên không hợp lệ — đã bỏ")
            changed = True
            continue
        if name in _RESERVED_NAMES:
            report.repairs.append(
                f"Parameter '{name}' trùng tên hàm/hằng built-in (pi, sin, ...) — đã bỏ"
            )
            changed = True
            continue
        try:
            mn = float(p.get("min"))
            mx = float(p.get("max"))
            df = float(p.get("default"))
        except (TypeError, ValueError):
            report.repairs.append(
                f"Parameter '{name}' min/max/default không phải số — đã bỏ"
            )
            changed = True
            continue
        if mx <= mn:
            report.repairs.append(
                f"Parameter '{name}' min={mn} >= max={mx} — đã chỉnh max = min + 1"
            )
            mx = mn + 1.0
            changed = True
        if not (mn <= df <= mx):
            report.repairs.append(
                f"Parameter '{name}' default={df} ngoài [{mn}, {mx}] — đã clamp về {max(mn, min(mx, df))}"
            )
            df = max(mn, min(mx, df))
            changed = True
        try:
            step = float(p.get("step", 0.1))
        except (TypeError, ValueError):
            step = 0.1
        if step <= 0:
            step = 0.1
        new_params.append({
            "name": name.strip(),
            "label": p.get("label") if isinstance(p.get("label"), str) else None,
            "min": mn,
            "max": mx,
            "default": df,
            "step": step,
        })
        param_names.add(name.strip())
    if changed or len(new_params) != len(params):
        data["parameters"] = new_params

    # Validate *_expr trong objects
    for obj in data.get("objects", []):
        for key in ("x_expr", "y_expr", "z_expr", "radius_expr"):
            expr = obj.get(key)
            if not isinstance(expr, str) or not expr.strip():
                if key in obj:
                    obj[key] = None
                continue
            free = _expr_free_names(expr)
            unknown = free - param_names
            if unknown:
                report.repairs.append(
                    f"Object '{obj.get('name') or obj.get('type')}' {key}='{expr}' "
                    f"tham chiếu biến không khai báo: {sorted(unknown)} — đã bỏ expression"
                )
                obj[key] = None
                changed = True

    if changed:
        return MathScene.model_validate(data)
    return scene


# ---------------------------------------------------------------------------
# 6. Annotation shape normalization
# ---------------------------------------------------------------------------


def _normalize_annotations(scene: MathScene, report: ValidationReport) -> MathScene:
    """Sửa nhanh một số shape annotation phổ biến LLM hay viết sai.

    - right_angle/angle có target dài hơn 1 ký tự + không có arms → cố gắng
      tách 'ABC' → target='B', arms=['A','C'].
    - length/equal_marks có target = 'AB' (không có '-') → '-A-B'.
    - Annotation thiếu metadata.arms cho angle/right_angle → drop.
    """
    data = scene.model_dump()
    changed = False
    new_anns: list[dict] = []
    points = _collect_point_names(scene)
    for ann in data.get("annotations", []):
        atype = ann.get("type")
        target = ann.get("target") or ""
        metadata = ann.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
            changed = True
        # Luôn gán lại để metadata là cùng tham chiếu với ann["metadata"]
        ann["metadata"] = metadata

        if atype in {"length", "equal_marks"} and isinstance(target, str):
            new_target = _normalize_segment_target(target)
            if new_target != target:
                ann["target"] = new_target
                changed = True
                report.repairs.append(
                    f"Annotation {atype}: target '{target}' → '{new_target}'"
                )

        if atype in {"right_angle", "angle"}:
            arms = metadata.get("arms")
            if isinstance(arms, str):
                parts = [p.strip() for p in re.split(r"[,;\-\s]+", arms) if p.strip()]
                if len(parts) >= 2:
                    metadata["arms"] = parts[:2]
                    changed = True
            arms = metadata.get("arms")
            # Tự động phân tách 'ABC' nếu target dài 3 + không có arms hợp lệ
            if (
                isinstance(target, str)
                and len(target) == 3
                and target.isupper()
                and (not isinstance(arms, list) or len(arms) != 2)
            ):
                center = target[1]
                a, b = target[0], target[2]
                if center in points and a in points and b in points:
                    ann["target"] = center
                    metadata["arms"] = [a, b]
                    changed = True
                    report.repairs.append(
                        f"Annotation {atype}: target '{target}' → '{center}', arms=['{a}','{b}']"
                    )
            arms = metadata.get("arms")
            if not isinstance(arms, list) or len(arms) != 2:
                report.warnings.append(
                    f"Annotation {atype} target='{ann.get('target')}' thiếu metadata.arms hợp lệ — đã bỏ"
                )
                changed = True
                continue

        new_anns.append(ann)

    if changed:
        data["annotations"] = new_anns
        return MathScene.model_validate(data)
    return scene


def _normalize_segment_target(target: str) -> str:
    compact = re.sub(r"\s+", "", target)
    if "-" in compact:
        parts = [p for p in compact.split("-") if p]
        if len(parts) >= 2:
            return f"{parts[0]}-{parts[1]}"
    if len(compact) == 2 and compact[0].isalpha() and compact[1].isalpha():
        return f"{compact[0]}-{compact[1]}"
    return target


__all__ = [
    "ValidationReport",
    "pre_validate_raw",
    "validate_and_repair",
]
