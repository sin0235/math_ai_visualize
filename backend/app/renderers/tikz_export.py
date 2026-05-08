"""Xuất MathScene sang TikZ (LaTeX) — dùng được trong Word/Overleaf.

Quy ước trục:
- Scene 2D: dùng trực tiếp (x, y).
- Scene 3D: chiếu xiên (oblique) đơn giản: x' = x + 0.5*y*cos(α), y' = z + 0.5*y*sin(α)
  với α = 30° (để mặt đáy trông có chiều sâu, S/A nằm đúng vị trí trực quan).

Các đối tượng hỗ trợ: point_2d/3d, segment, line_2d/3d, circle_2d, vector_2d/3d,
face (đa giác fill mờ), sphere/plane (skip cho TikZ vì khó render đúng tỷ lệ).
Annotations: length, angle (label đơn giản), right_angle (vẽ ô vuông nhỏ tại
đỉnh).

Xuất ra một chuỗi LaTeX hoàn chỉnh trong môi trường ``tikzpicture``; user copy
trực tiếp vào file .tex (đã có \\usepackage{tikz}).
"""

from __future__ import annotations

from math import cos, pi, sin
from typing import Iterable

from app.schemas.scene import (
    Annotation,
    Circle2D,
    Face,
    Line2D,
    Line3D,
    MathScene,
    Point2D,
    Point3D,
    Segment,
    Vector2D,
    Vector3D,
)

OBLIQUE_ANGLE_DEG = 30
OBLIQUE_SCALE = 0.5
DASH_PATTERN = "dashed"


def _project(p: Point2D | Point3D) -> tuple[float, float]:
    if isinstance(p, Point2D):
        return (p.x, p.y)
    a = pi * OBLIQUE_ANGLE_DEG / 180.0
    return (p.x + OBLIQUE_SCALE * p.y * cos(a), p.z + OBLIQUE_SCALE * p.y * sin(a))


def _fmt(v: float) -> str:
    if abs(v - round(v)) < 1e-6:
        return f"{int(round(v))}"
    return f"{v:.3f}".rstrip("0").rstrip(".")


def _coord(p: tuple[float, float]) -> str:
    return f"({_fmt(p[0])},{_fmt(p[1])})"


def _hex_to_rgb(color: str | None) -> tuple[int, int, int] | None:
    if not color or not color.startswith("#") or len(color) != 7:
        return None
    try:
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        return (r, g, b)
    except ValueError:
        return None


def _color_def(name: str, hex_color: str) -> str:
    rgb = _hex_to_rgb(hex_color)
    if rgb is None:
        return ""
    return f"\\definecolor{{{name}}}{{RGB}}{{{rgb[0]},{rgb[1]},{rgb[2]}}}"


def _line_options(color_name: str | None, dashed: bool, thick: bool = True) -> str:
    parts: list[str] = []
    if thick:
        parts.append("thick")
    if dashed:
        parts.append(DASH_PATTERN)
    if color_name:
        parts.append(f"draw={color_name}")
    return ",".join(parts)


def build_tikz(scene: MathScene) -> str:
    """Trả về chuỗi LaTeX trong môi trường ``tikzpicture`` (chưa wrap document)."""
    points: dict[str, Point2D | Point3D] = {
        obj.name: obj for obj in scene.objects if isinstance(obj, (Point2D, Point3D))
    }

    color_defs: list[str] = []
    seen_colors: dict[str, str] = {}

    def _ensure_color(hex_color: str | None) -> str | None:
        if not hex_color:
            return None
        key = hex_color.lower()
        if key in seen_colors:
            return seen_colors[key]
        idx = len(seen_colors)
        name = f"hinhc{idx}"
        defn = _color_def(name, hex_color)
        if defn:
            color_defs.append(defn)
            seen_colors[key] = name
            return name
        return None

    body_lines: list[str] = []

    # Faces (vẽ trước để các segment đè lên trên)
    for obj in scene.objects:
        if isinstance(obj, Face):
            coords = [_coord(_project(points[name])) for name in obj.points if name in points]
            if len(coords) < 3:
                continue
            color = _ensure_color(obj.color)
            opacity = max(0.0, min(1.0, obj.opacity))
            opts = []
            if color:
                opts.append(f"fill={color}")
            opts.append(f"fill opacity={opacity:.2f}")
            opts.append("draw=none")
            body_lines.append(f"  \\fill[{','.join(opts)}] " + " -- ".join(coords) + " -- cycle;")

    # Segments + lines + vectors
    for obj in scene.objects:
        if isinstance(obj, Segment):
            if obj.points[0] not in points or obj.points[1] not in points:
                continue
            a = _coord(_project(points[obj.points[0]]))
            b = _coord(_project(points[obj.points[1]]))
            dashed = obj.style in ("dashed", "dotted") or obj.hidden
            color = _ensure_color(obj.color)
            opts = _line_options(color, dashed)
            body_lines.append(f"  \\draw[{opts}] {a} -- {b};")
        elif isinstance(obj, Line2D):
            if obj.through[0] not in points or obj.through[1] not in points:
                continue
            a = _project(points[obj.through[0]])
            b = _project(points[obj.through[1]])
            # Mở rộng line trong khoảng nhìn thấy: kéo dài 1.5x
            dx, dy = b[0] - a[0], b[1] - a[1]
            ext_a = (a[0] - 0.5 * dx, a[1] - 0.5 * dy)
            ext_b = (b[0] + 0.5 * dx, b[1] + 0.5 * dy)
            body_lines.append(f"  \\draw[thick] {_coord(ext_a)} -- {_coord(ext_b)};")
        elif isinstance(obj, Line3D):
            if obj.through[0] not in points or obj.through[1] not in points:
                continue
            a = _coord(_project(points[obj.through[0]]))
            b = _coord(_project(points[obj.through[1]]))
            color = _ensure_color(obj.color)
            opts = _line_options(color, dashed=False)
            body_lines.append(f"  \\draw[{opts}] {a} -- {b};")
        elif isinstance(obj, (Vector2D, Vector3D)):
            if obj.from_point not in points or obj.to_point not in points:
                continue
            a = _coord(_project(points[obj.from_point]))
            b = _coord(_project(points[obj.to_point]))
            color = _ensure_color(getattr(obj, "color", None))
            opts = "->,thick"
            if color:
                opts += f",draw={color}"
            body_lines.append(f"  \\draw[{opts}] {a} -- {b};")
        elif isinstance(obj, Circle2D) and isinstance(points.get(obj.center), Point2D):
            center = _project(points[obj.center])
            radius = obj.radius
            if radius is None and obj.through and obj.through in points:
                tp = _project(points[obj.through])
                radius = ((tp[0] - center[0]) ** 2 + (tp[1] - center[1]) ** 2) ** 0.5
            if radius:
                body_lines.append(f"  \\draw[thick] {_coord(center)} circle ({_fmt(radius)});")

    # Points
    for obj in scene.objects:
        if isinstance(obj, (Point2D, Point3D)):
            xy = _project(obj)
            body_lines.append(f"  \\fill {_coord(xy)} circle (1.5pt) node[above right] {{${obj.name}$}};")

    # Annotations
    for ann in scene.annotations:
        line = _annotation_to_tikz(ann, points)
        if line:
            body_lines.append("  " + line)

    header_opts = "scale=1.0,every node/.style={font=\\small}"
    out: list[str] = []
    out.extend(color_defs)
    out.append(f"\\begin{{tikzpicture}}[{header_opts}]")
    out.extend(body_lines)
    out.append("\\end{tikzpicture}")
    return "\n".join(out)


def _annotation_to_tikz(
    ann: Annotation, points: dict[str, Point2D | Point3D]
) -> str | None:
    if ann.type == "length" and "-" in ann.target:
        a_name, b_name = ann.target.split("-", 1)
        if a_name in points and b_name in points:
            mid = (
                (_project(points[a_name])[0] + _project(points[b_name])[0]) / 2,
                (_project(points[a_name])[1] + _project(points[b_name])[1]) / 2,
            )
            label = ann.label or ""
            if not label:
                return None
            return f"\\node[fill=white,inner sep=1pt] at {_coord(mid)} {{${_escape_label(label)}$}};"
    elif ann.type == "right_angle" and ann.target in points:
        # Vẽ ô vuông nhỏ tại đỉnh, kích thước 0.2; arms phải có 2 điểm
        arms = ann.metadata.get("arms") or []
        if len(arms) != 2 or arms[0] not in points or arms[1] not in points:
            return None
        v = _project(points[ann.target])
        a = _project(points[arms[0]])
        b = _project(points[arms[1]])
        # Vector đơn vị từ v ra a và v ra b, scale 0.2
        size = 0.2
        ua = _scaled_unit(v, a, size)
        ub = _scaled_unit(v, b, size)
        if ua is None or ub is None:
            return None
        p1 = (v[0] + ua[0], v[1] + ua[1])
        p2 = (p1[0] + ub[0], p1[1] + ub[1])
        p3 = (v[0] + ub[0], v[1] + ub[1])
        return (
            f"\\draw {_coord(p1)} -- {_coord(p2)} -- {_coord(p3)};"
        )
    elif ann.type == "angle" and ann.target in points and ann.label:
        # Đơn giản: đặt label cạnh đỉnh
        v = _project(points[ann.target])
        return f"\\node[font=\\footnotesize] at ({_fmt(v[0] + 0.2)},{_fmt(v[1] + 0.2)}) {{${_escape_label(ann.label)}$}};"
    return None


def _scaled_unit(
    origin: tuple[float, float], target: tuple[float, float], length: float
) -> tuple[float, float] | None:
    dx, dy = target[0] - origin[0], target[1] - origin[1]
    norm = (dx * dx + dy * dy) ** 0.5
    if norm < 1e-9:
        return None
    return (length * dx / norm, length * dy / norm)


def _escape_label(label: str) -> str:
    # Tránh ký tự đặc biệt cơ bản. Người dùng tự chỉnh nếu muốn LaTeX phức tạp.
    return label.replace("°", "^{\\circ}").replace("&", "\\&")


def build_tikz_document(scene: MathScene, problem_text: str | None = None) -> str:
    """Wrap TikZ trong document LaTeX standalone (compile được trực tiếp)."""
    body = build_tikz(scene)
    title = problem_text or scene.problem_text or "Hình"
    title_escaped = title.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
    return (
        "\\documentclass[border=10pt]{standalone}\n"
        "\\usepackage{tikz}\n"
        "\\usepackage{xcolor}\n"
        "\\usepackage[utf8]{inputenc}\n"
        "\\usepackage[T5]{fontenc}\n"
        "\\begin{document}\n"
        f"% {title_escaped}\n"
        f"{body}\n"
        "\\end{document}\n"
    )


__all__ = ["build_tikz", "build_tikz_document"]
