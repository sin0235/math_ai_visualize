from typing import Any

from app.schemas.scene import Annotation, Face, Line3D, MathScene, Plane, Point3D, Relation, Segment, Sphere, Vector3D
from app.services.geometry_engine import compute_three_geometry


def build_three_scene(scene: MathScene) -> dict[str, Any]:
    points = {
        obj.name: {"x": obj.x, "y": obj.y, "z": obj.z}
        for obj in scene.objects
        if isinstance(obj, Point3D)
    }
    segments = [
        {
            "points": obj.points,
            "hidden": obj.hidden,
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
        if isinstance(obj, Face)
    ]
    spheres = [
        {"center": obj.center, "radius": obj.radius, "name": obj.name, "color": obj.color, "opacity": obj.opacity}
        for obj in scene.objects
        if isinstance(obj, Sphere)
    ]
    lines = [
        {"through": obj.through, "name": obj.name, "color": obj.color}
        for obj in scene.objects
        if isinstance(obj, Line3D)
    ]
    vectors = [
        {"from_point": obj.from_point, "to_point": obj.to_point, "name": obj.name, "color": obj.color}
        for obj in scene.objects
        if isinstance(obj, Vector3D)
    ]
    planes = [
        {"points": obj.points, "name": obj.name, "color": obj.color, "opacity": obj.opacity, "show_normal": obj.show_normal}
        for obj in scene.objects
        if isinstance(obj, Plane)
    ]
    computed = compute_three_geometry(scene)
    annotations = [
        ann.model_dump() for ann in scene.annotations
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
