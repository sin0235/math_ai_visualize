from typing import Any

from app.schemas.render_projection_v3 import RenderProjectionV3
from app.schemas.scene import Annotation, Face, Line3D, MathScene, Plane, Point3D, Relation, Segment, Sphere, Vector3D
from app.services.geometry_engine import compute_three_geometry
from app.services.scene_trust import trusted_display_annotations


def build_three_scene_v3(projection: RenderProjectionV3) -> dict[str, Any]:
    return {
        "schema_version": "3.0",
        "scene_id": projection.scene_id,
        "revision": projection.revision,
        "object_names": projection.object_names,
        "points": {
            point.object_id: {
                "object_id": point.object_id,
                "name": point.name,
                "label": point.label,
                "x": point.position[0],
                "y": point.position[1],
                "z": point.position[2],
                "visible": point.visible,
            }
            for point in projection.points
        },
        "segments": [item.model_dump(mode="json") for item in projection.linear if item.kind == "segment"],
        "lines": [item.model_dump(mode="json") for item in projection.linear if item.kind == "line"],
        "vectors": [item.model_dump(mode="json") for item in projection.linear if item.kind == "vector"],
        "circles": [item.model_dump(mode="json") for item in projection.circles],
        "functions": [item.model_dump(mode="json") for item in projection.functions],
        "surfaces": [item.model_dump(mode="json") for item in projection.surfaces],
        "spheres": [item.model_dump(mode="json") for item in projection.spheres],
        "annotations": [item.model_dump(mode="json") for item in projection.annotations],
        "bounds": projection.bounds.model_dump(mode="json"),
        "view": projection.view.model_dump(mode="json"),
    }


def build_three_scene(scene: MathScene) -> dict[str, Any]:
    points = {
        obj.name: {"x": obj.x, "y": obj.y, "z": obj.z, "hidden": bool(obj.metadata.get("tree_hidden"))}
        for obj in scene.objects
        if isinstance(obj, Point3D)
    }
    segments = [
        {
            "points": obj.points,
            "hidden": obj.hidden or bool(obj.metadata.get("tree_hidden")),
            "name": obj.name,
            "color": obj.color,
            "line_width": obj.line_width,
            "style": obj.style,
        }
        for obj in scene.objects
        if isinstance(obj, Segment)
    ]
    faces = [
        {"points": obj.points, "name": obj.name, "color": obj.color, "opacity": obj.opacity}
        for obj in scene.objects
        if isinstance(obj, Face) and not obj.metadata.get("tree_hidden")
    ]
    spheres = [
        {"center": obj.center, "radius": obj.radius, "name": obj.name, "color": obj.color, "opacity": obj.opacity}
        for obj in scene.objects
        if isinstance(obj, Sphere) and not obj.metadata.get("tree_hidden")
    ]
    lines = [
        {"through": obj.through, "name": obj.name, "color": obj.color}
        for obj in scene.objects
        if isinstance(obj, Line3D) and not obj.metadata.get("tree_hidden")
    ]
    vectors = [
        {"from_point": obj.from_point, "to_point": obj.to_point, "name": obj.name, "color": obj.color}
        for obj in scene.objects
        if isinstance(obj, Vector3D) and not obj.metadata.get("tree_hidden")
    ]
    planes = [
        {"points": obj.points, "name": obj.name, "color": obj.color, "opacity": obj.opacity, "show_normal": obj.show_normal}
        for obj in scene.objects
        if isinstance(obj, Plane) and not obj.metadata.get("tree_hidden")
    ]
    computed = compute_three_geometry(scene)
    annotations = [
        ann.model_dump() for ann in trusted_display_annotations(scene.annotations)
        if not ann.metadata.get("tree_hidden")
    ]
    relations = [
        rel.model_dump() for rel in scene.relations
    ]

    return {
        "points": points,
        "segments": segments,
        "faces": faces,
        "spheres": spheres,
        "lines": lines,
        "vectors": vectors,
        "planes": planes,
        "computed": computed,
        "annotations": annotations,
        "relations": relations,
        "view": scene.view.model_dump(),
    }
