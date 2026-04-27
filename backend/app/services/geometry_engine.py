import math
from typing import Any

from app.schemas.scene import Annotation, Face, MathScene, Point3D, Segment


def normalize_scene(scene: MathScene) -> MathScene:
    if scene.renderer != "threejs_3d":
        return scene

    data = scene.model_dump()

    # ---- auto-generate segments from faces ----
    point_names = {obj.name for obj in scene.objects if isinstance(obj, Point3D)}
    existing_edges = {
        _edge_key(obj.points[0], obj.points[1])
        for obj in scene.objects
        if isinstance(obj, Segment)
    }
    new_segments: list[dict[str, Any]] = []

    for face in [obj for obj in scene.objects if isinstance(obj, Face)]:
        for start, end in _face_edges(face.points):
            if start not in point_names or end not in point_names:
                continue
            key = _edge_key(start, end)
            if key in existing_edges:
                continue
            existing_edges.add(key)
            new_segments.append({
                "type": "segment",
                "points": [start, end],
                "hidden": _looks_hidden_edge(start, end, scene),
            })

    if new_segments:
        data["objects"] = [*data["objects"], *new_segments]

    # ---- auto-generate coordinate_label annotations if show_coordinates ----
    if scene.view.show_coordinates:
        existing_coord_targets = {
            ann.target for ann in scene.annotations if ann.type == "coordinate_label"
        }
        for obj in scene.objects:
            if isinstance(obj, Point3D) and obj.name not in existing_coord_targets:
                data["annotations"].append({
                    "type": "coordinate_label",
                    "target": obj.name,
                    "metadata": {},
                })

    return MathScene.model_validate(data)


def _face_edges(points: list[str]) -> list[tuple[str, str]]:
    return [(points[index], points[(index + 1) % len(points)]) for index in range(len(points))]


def _edge_key(start: str, end: str) -> tuple[str, str]:
    return tuple(sorted((start, end)))


def _looks_hidden_edge(start: str, end: str, scene: MathScene) -> bool:
    """Heuristic: edges connecting 'back' points are drawn dashed.

    For typical solid geometry figures viewed from front-right-top,
    edges involving D (and D') in a box, or edges on the 'far' side
    of a base polygon tend to be hidden.
    """
    points_map = {obj.name: obj for obj in scene.objects if isinstance(obj, Point3D)}
    p1 = points_map.get(start)
    p2 = points_map.get(end)

    if not p1 or not p2:
        return False

    # Edges on the far side in z (positive z = away from default camera)
    both_far_z = p1.z > 0.5 and p2.z > 0.5
    # Or edges that go from a far-z bottom point to another far-z bottom point
    if both_far_z and p1.y < 0.1 and p2.y < 0.1:
        return True

    # Vertical edges at far-z positions
    if abs(p1.x - p2.x) < 0.01 and abs(p1.z - p2.z) < 0.01 and p1.z > 0.5:
        return True

    return False
