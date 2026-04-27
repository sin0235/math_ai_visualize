from typing import Any

from app.schemas.scene import Annotation, Face, MathScene, Point3D, Relation, Segment, Sphere


def build_three_scene(scene: MathScene) -> dict[str, Any]:
    points = {
        obj.name: {"x": obj.x, "y": obj.y, "z": obj.z}
        for obj in scene.objects
        if isinstance(obj, Point3D)
    }
    segments = [
        {"points": obj.points, "hidden": obj.hidden, "name": obj.name}
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
        "annotations": annotations,
        "relations": relations,
        "view": scene.view.model_dump(),
    }
