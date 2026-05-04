import re
from dataclasses import dataclass
from itertools import combinations

from app.schemas.scene import (
    AdvancedRenderSettings,
    Circle2D,
    Face,
    FunctionGraph,
    Line2D,
    Line3D,
    MathScene,
    Plane,
    Point2D,
    Point3D,
    Segment,
    Sphere,
    Vector2D,
    Vector3D,
)

_SAFE_EXPRESSION_RE = re.compile(r"^[0-9xXyY+\-*/^()., sincostanlogsqrt abs]+$")
_HEX_COLOR_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")
_LINE_STYLE_CODES = {"solid": 0, "dashed": 1, "dotted": 2}


@dataclass(frozen=True)
class LabelPosition:
    name: str
    commands: list[str]


def build_geogebra_commands(scene: MathScene, settings: AdvancedRenderSettings | None = None) -> list[str]:
    settings = settings or AdvancedRenderSettings()
    commands: list[str] = []
    intersectable_names: list[str] = []
    line_count = 0
    line3d_count = 0
    circle_count = 0
    segment_count = 0
    vector_count = 0
    vector3d_count = 0
    plane_count = 0
    sphere_count = 0
    face_count = 0
    show_coordinates = settings.show_coordinates if settings.show_coordinates is not None else scene.view.show_coordinates

    for obj in scene.objects:
        if isinstance(obj, Point2D):
            commands.append(f"{obj.name} = ({obj.x}, {obj.y})")
            if show_coordinates:
                commands.extend(_coordinate_label_commands(obj.name, f"{obj.name} = ({_format_number(obj.x)}, {_format_number(obj.y)})"))
        elif isinstance(obj, Point3D):
            commands.append(f"{obj.name} = ({obj.x}, {obj.y}, {obj.z})")
            if show_coordinates:
                commands.extend(_coordinate_label_commands(obj.name, f"{obj.name} = ({_format_number(obj.x)}, {_format_number(obj.y)}, {_format_number(obj.z)})"))
        elif isinstance(obj, Line2D):
            line_count += 1
            name = obj.name or f"d{line_count}"
            commands.append(f"{name} = Line({obj.through[0]}, {obj.through[1]})")
            intersectable_names.append(name)
        elif isinstance(obj, Line3D):
            line3d_count += 1
            name = obj.name or f"l{line3d_count}"
            commands.append(f"{name} = Line({obj.through[0]}, {obj.through[1]})")
            commands.extend(_style_commands(name, color=obj.color))
        elif isinstance(obj, Segment):
            segment_count += 1
            name = obj.name or f"s{segment_count}"
            commands.append(f"{name} = Segment({obj.points[0]}, {obj.points[1]})")
            commands.extend(_segment_style_commands(name, obj))
        elif isinstance(obj, Vector2D):
            vector_count += 1
            name = obj.name or f"v{vector_count}"
            commands.append(f"{name} = Vector({obj.from_point}, {obj.to_point})")
        elif isinstance(obj, Vector3D):
            vector3d_count += 1
            name = obj.name or f"v{vector3d_count}"
            commands.append(f"{name} = Vector({obj.from_point}, {obj.to_point})")
            commands.extend(_style_commands(name, color=obj.color))
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
        elif isinstance(obj, Plane):
            plane_count += 1
            name = obj.name or f"p{plane_count}"
            commands.append(f"{name} = Plane({', '.join(obj.points[:3])})")
            commands.extend(_style_commands(name, color=obj.color, opacity=obj.opacity))
        elif isinstance(obj, Sphere):
            sphere_count += 1
            name = obj.name or f"sphere{sphere_count}"
            commands.append(f"{name} = Sphere({obj.center}, {obj.radius})")
            commands.extend(_style_commands(name, color=obj.color, opacity=obj.opacity))
        elif isinstance(obj, Face):
            face_count += 1
            name = obj.name or f"poly{face_count}"
            commands.append(f"{name} = Polygon({', '.join(obj.points)})")
            commands.extend(_style_commands(name, color=obj.color, opacity=obj.opacity))

    commands.extend(_annotation_commands(scene))

    if settings.graph_intersections:
        for index, (first, second) in enumerate(combinations(intersectable_names, 2), start=1):
            commands.append(f"I{index} = Intersect({first}, {second})")

    return commands


def _annotation_commands(scene: MathScene) -> list[str]:
    commands: list[str] = []
    points = {obj.name: obj for obj in scene.objects if isinstance(obj, Point2D | Point3D)}
    label_count = 0
    angle_count = 0

    for annotation in scene.annotations:
        if annotation.type == "coordinate_label" and annotation.target in points:
            point = points[annotation.target]
            if isinstance(point, Point3D):
                caption = annotation.label or f"{point.name} = ({_format_number(point.x)}, {_format_number(point.y)}, {_format_number(point.z)})"
            else:
                caption = annotation.label or f"{point.name} = ({_format_number(point.x)}, {_format_number(point.y)})"
            commands.extend(_coordinate_label_commands(annotation.target, caption))
        elif annotation.type in {"length", "equal_marks"}:
            endpoints = _target_endpoints(annotation.target)
            if not endpoints or endpoints[0] not in points or endpoints[1] not in points:
                continue
            label_count += 1
            first_point = points[endpoints[0]]
            second_point = points[endpoints[1]]
            if annotation.type == "equal_marks":
                commands.extend(_equal_mark_commands(f"annTick{label_count}", first_point, second_point, annotation.color))
                continue
            text = _clean_product_label(annotation.label or annotation.target.replace("-", ""))
            label_position = _segment_label_position(f"annMid{label_count}", first_point, second_point, label_count)
            commands.extend(label_position.commands)
            commands.append(f'annText{label_count} = Text("{_escape_text(text)}", {label_position.name})')
            commands.extend(_style_commands(f"annText{label_count}", color=annotation.color or "#1d3557"))
        elif annotation.type in {"angle", "right_angle"}:
            arms = annotation.metadata.get("arms")
            if not isinstance(arms, list) or len(arms) < 2:
                continue
            first, second = str(arms[0]), str(arms[1])
            vertex = annotation.target
            if first not in points or vertex not in points or second not in points:
                continue
            angle_count += 1
            name = f"annAngle{angle_count}"
            commands.append(f"{name} = Angle({first}, {vertex}, {second})")
            if annotation.label:
                commands.append(f'SetCaption({name}, "{_escape_text(annotation.label)}")')
                commands.append(f"ShowLabel({name}, true)")
            if annotation.color:
                commands.extend(_style_commands(name, color=annotation.color))
    return commands


def _target_endpoints(target: str) -> tuple[str, str] | None:
    parts = [part.strip() for part in target.split("-") if part.strip()]
    if len(parts) == 2:
        return parts[0], parts[1]
    if len(target) == 2:
        return target[0], target[1]
    return None


def _segment_label_position(name: str, first: Point2D | Point3D, second: Point2D | Point3D, index: int) -> LabelPosition:
    first_x, first_y = _point_screen_xy(first)
    second_x, second_y = _point_screen_xy(second)
    dx = second_x - first_x
    dy = second_y - first_y
    length = max((dx * dx + dy * dy) ** 0.5, 1)
    side = 1 if index % 2 else -1
    offset = 0.28 * side
    x = (first_x + second_x) / 2 - (dy / length) * offset
    y = (first_y + second_y) / 2 + (dx / length) * offset
    commands = [f"{name} = ({_format_number(x)}, {_format_number(y)})"]
    return LabelPosition(name=name, commands=commands)


def _equal_mark_commands(name: str, first: Point2D | Point3D, second: Point2D | Point3D, color: str | None) -> list[str]:
    first_x, first_y = _point_screen_xy(first)
    second_x, second_y = _point_screen_xy(second)
    dx = second_x - first_x
    dy = second_y - first_y
    length = max((dx * dx + dy * dy) ** 0.5, 1)
    tick_half = min(0.12, length * 0.08)
    mid_x = (first_x + second_x) / 2
    mid_y = (first_y + second_y) / 2
    nx = -dy / length
    ny = dx / length
    start = f"{name}A"
    end = f"{name}B"
    segment = f"{name}Seg"
    commands = [
        f"{start} = ({_format_number(mid_x - nx * tick_half)}, {_format_number(mid_y - ny * tick_half)})",
        f"{end} = ({_format_number(mid_x + nx * tick_half)}, {_format_number(mid_y + ny * tick_half)})",
        f"{segment} = Segment({start}, {end})",
        f"ShowLabel({start}, false)",
        f"ShowLabel({end}, false)",
    ]
    commands.extend(_style_commands(segment, color=color or "#e63946", line_width=2))
    return commands


def _point_screen_xy(point: Point2D | Point3D) -> tuple[float, float]:
    if isinstance(point, Point3D):
        return point.x, point.y
    return point.x, point.y


def _clean_product_label(value: str) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    text = text.replace("metadata", "").replace("relation", "")
    return text[:24]


def _coordinate_label_commands(name: str, caption: str) -> list[str]:
    return [f'SetCaption({name}, "{_escape_text(caption)}")', f"ShowLabel({name}, true)"]


def _escape_text(value: str) -> str:
    return value.replace('\\', '\\\\').replace('"', '\\"')


def _segment_style_commands(name: str, segment: Segment) -> list[str]:
    commands = _style_commands(name, color=segment.color, line_width=segment.line_width)
    if segment.style:
        commands.append(f"SetLineStyle({name}, {_LINE_STYLE_CODES[segment.style]})")
    if segment.hidden:
        commands.append(f"SetVisibleInView({name}, 1, false)")
        commands.append(f"SetVisibleInView({name}, 2, false)")
    return commands


def _style_commands(name: str, color: str | None = None, line_width: float | None = None, opacity: float | None = None) -> list[str]:
    commands: list[str] = []
    parsed_color = _parse_hex_color(color)
    if parsed_color:
        commands.append(f'SetColor({name}, "{parsed_color}")')
    if line_width is not None:
        commands.append(f"SetLineThickness({name}, {_line_thickness(line_width)})")
    if opacity is not None:
        commands.append(f"SetFilling({name}, {_opacity(opacity)})")
    return commands


def _parse_hex_color(color: str | None) -> str | None:
    if not color:
        return None
    match = _HEX_COLOR_RE.fullmatch(color.strip())
    if not match:
        return None
    return f"#{match.group(1).lower()}"


def _line_thickness(value: float) -> int:
    return max(1, min(13, round(value)))


def _opacity(value: float) -> float:
    return max(0, min(1, value))


def _format_number(value: float) -> str:
    return f"{value:g}"
