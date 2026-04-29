import re
from itertools import combinations

from app.schemas.scene import AdvancedRenderSettings, Circle2D, FunctionGraph, Line2D, MathScene, Point2D, Segment, Vector2D

_SAFE_EXPRESSION_RE = re.compile(r"^[0-9xXyY+\-*/^()., sincostanlogsqrt abs]+$")


def build_geogebra_commands(scene: MathScene, settings: AdvancedRenderSettings | None = None) -> list[str]:
    settings = settings or AdvancedRenderSettings()
    commands: list[str] = []
    intersectable_names: list[str] = []
    line_count = 0
    circle_count = 0

    for obj in scene.objects:
        if isinstance(obj, Point2D):
            commands.append(f"{obj.name} = ({obj.x}, {obj.y})")
        elif isinstance(obj, Line2D):
            line_count += 1
            name = obj.name or f"d{line_count}"
            commands.append(f"{name} = Line({obj.through[0]}, {obj.through[1]})")
            intersectable_names.append(name)
        elif isinstance(obj, Segment):
            commands.append(f"Segment({obj.points[0]}, {obj.points[1]})")
        elif isinstance(obj, Vector2D):
            commands.append(f"Vector({obj.from_point}, {obj.to_point})")
        elif isinstance(obj, Circle2D):
            circle_count += 1
            name = obj.name or f"c{circle_count}"
            if obj.through:
                commands.append(f"{name} = Circle({obj.center}, {obj.through})")
                intersectable_names.append(name)
            elif obj.radius is not None:
                commands.append(f"{name} = Circle({obj.center}, {obj.radius})")
                intersectable_names.append(name)
        elif isinstance(obj, FunctionGraph):
            expression = obj.expression.replace(" ", "")
            if _SAFE_EXPRESSION_RE.fullmatch(expression):
                commands.append(f"{obj.name}(x) = {expression}")
                intersectable_names.append(obj.name)

    if settings.graph_intersections:
        for index, (first, second) in enumerate(combinations(intersectable_names, 2), start=1):
            commands.append(f"I{index} = Intersect({first}, {second})")

    return commands
