import re

from app.schemas.scene import Circle2D, FunctionGraph, Line2D, MathScene, Point2D, Segment, Vector2D

_SAFE_EXPRESSION_RE = re.compile(r"^[0-9xXyY+\-*/^()., sincostanlogsqrt abs]+$")


def build_geogebra_commands(scene: MathScene) -> list[str]:
    commands: list[str] = []

    for obj in scene.objects:
        if isinstance(obj, Point2D):
            commands.append(f"{obj.name} = ({obj.x}, {obj.y})")
        elif isinstance(obj, Line2D):
            commands.append(f"{obj.name or 'd'} = Line({obj.through[0]}, {obj.through[1]})")
        elif isinstance(obj, Segment):
            commands.append(f"Segment({obj.points[0]}, {obj.points[1]})")
        elif isinstance(obj, Vector2D):
            commands.append(f"Vector({obj.from_point}, {obj.to_point})")
        elif isinstance(obj, Circle2D):
            if obj.through:
                commands.append(f"{obj.name or 'c'} = Circle({obj.center}, {obj.through})")
            elif obj.radius is not None:
                commands.append(f"{obj.name or 'c'} = Circle({obj.center}, {obj.radius})")
        elif isinstance(obj, FunctionGraph):
            expression = obj.expression.replace(" ", "")
            if _SAFE_EXPRESSION_RE.fullmatch(expression):
                commands.append(f"{obj.name}(x) = {expression}")

    return commands
