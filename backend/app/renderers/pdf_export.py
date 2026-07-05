"""Xuất MathScene sang PDF dùng matplotlib (2D thuần) và 3D oblique projection.

Mục tiêu: 1 trang in được, header là đề bài, body là hình. Đầu vào lấy từ
MathScene đã normalize (giá trị float, không expression). Hỗ trợ:
- Point (vẽ chấm + label)
- Segment (solid/dashed theo style + hidden flag)
- Face (polygon mờ)
- Circle 2D
- Line 2D/3D
- Vector 2D/3D
- Annotations: length, right_angle (chỉ 2D/projected 3D)

Đối với 3D dùng cùng oblique projection như TikZ (α = 30°, scale 0.5) để dễ
nhận ra khối; không thử rendering thực tế shading vì scope là "snapshot in được".
"""

from __future__ import annotations

import base64
import binascii
import io
from math import cos, pi, sin

import matplotlib

matplotlib.use("Agg")  # headless

import matplotlib.patches as mpatches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

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
    RenderResponse,
    ExportViewCapture,
)
from app.services.scene_trust import export_notice_lines, scene_with_trusted_annotations

OBLIQUE_ANGLE_DEG = 30
OBLIQUE_SCALE = 0.5


def _project(p: Point2D | Point3D) -> tuple[float, float]:
    if isinstance(p, Point2D):
        return (p.x, p.y)
    a = pi * OBLIQUE_ANGLE_DEG / 180.0
    return (p.x + OBLIQUE_SCALE * p.y * cos(a), p.z + OBLIQUE_SCALE * p.y * sin(a))


def _wrap_text(text: str, max_chars: int = 80) -> str:
    if not text:
        return ""
    words = text.split()
    out: list[str] = []
    line = ""
    for w in words:
        if len(line) + len(w) + 1 > max_chars:
            out.append(line.rstrip())
            line = ""
        line += w + " "
    if line:
        out.append(line.rstrip())
    return "\n".join(out)


def _draw_scene(scene: MathScene, ax: plt.Axes) -> None:
    points: dict[str, Point2D | Point3D] = {
        obj.name: obj for obj in scene.objects if isinstance(obj, (Point2D, Point3D))
    }

    # Faces
    for obj in scene.objects:
        if isinstance(obj, Face):
            coords = [_project(points[name]) for name in obj.points if name in points]
            if len(coords) < 3:
                continue
            poly = mpatches.Polygon(
                coords,
                closed=True,
                facecolor=obj.color,
                edgecolor="none",
                alpha=max(0.0, min(1.0, obj.opacity)),
            )
            ax.add_patch(poly)

    # Segments / lines / vectors / circles
    for obj in scene.objects:
        if isinstance(obj, Segment):
            if obj.points[0] not in points or obj.points[1] not in points:
                continue
            a = _project(points[obj.points[0]])
            b = _project(points[obj.points[1]])
            dashed = obj.style in ("dashed", "dotted") or obj.hidden
            ax.plot(
                [a[0], b[0]],
                [a[1], b[1]],
                color=obj.color or "#1d3557",
                linewidth=(obj.line_width or 1.6),
                linestyle=("--" if dashed else "-"),
            )
        elif isinstance(obj, Line2D):
            if obj.through[0] not in points or obj.through[1] not in points:
                continue
            a = _project(points[obj.through[0]])
            b = _project(points[obj.through[1]])
            dx, dy = b[0] - a[0], b[1] - a[1]
            ext_a = (a[0] - 0.5 * dx, a[1] - 0.5 * dy)
            ext_b = (b[0] + 0.5 * dx, b[1] + 0.5 * dy)
            ax.plot(
                [ext_a[0], ext_b[0]],
                [ext_a[1], ext_b[1]],
                color="#1d3557",
                linewidth=1.4,
            )
        elif isinstance(obj, Line3D):
            if obj.through[0] not in points or obj.through[1] not in points:
                continue
            a = _project(points[obj.through[0]])
            b = _project(points[obj.through[1]])
            ax.plot([a[0], b[0]], [a[1], b[1]], color=obj.color or "#1d3557", linewidth=1.4)
        elif isinstance(obj, (Vector2D, Vector3D)):
            if obj.from_point not in points or obj.to_point not in points:
                continue
            a = _project(points[obj.from_point])
            b = _project(points[obj.to_point])
            ax.annotate(
                "",
                xy=b,
                xytext=a,
                arrowprops=dict(
                    arrowstyle="->",
                    color=getattr(obj, "color", "#7c3aed"),
                    lw=1.6,
                ),
            )
        elif isinstance(obj, Circle2D) and isinstance(points.get(obj.center), Point2D):
            center = _project(points[obj.center])
            radius = obj.radius
            if radius is None and obj.through and obj.through in points:
                tp = _project(points[obj.through])
                radius = ((tp[0] - center[0]) ** 2 + (tp[1] - center[1]) ** 2) ** 0.5
            if radius:
                circle = mpatches.Circle(center, radius, fill=False, color="#1d3557", linewidth=1.4)
                ax.add_patch(circle)

    # Points (sau cùng để nằm trên mọi shape)
    for name, p in points.items():
        x, y = _project(p)
        ax.plot(x, y, "o", color="#0b0c10", markersize=4)
        ax.annotate(
            f"${name}$",
            xy=(x, y),
            xytext=(6, 6),
            textcoords="offset points",
            fontsize=12,
            fontweight="bold",
        )

    # Annotations
    for ann in scene.annotations:
        _draw_annotation(ann, points, ax)

    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(scene.view.show_grid, linestyle=":", alpha=0.3)
    if scene.view.show_axes:
        ax.axhline(0, color="#999", linewidth=0.5)
        ax.axvline(0, color="#999", linewidth=0.5)


def _draw_annotation(
    ann: Annotation, points: dict[str, Point2D | Point3D], ax: plt.Axes
) -> None:
    if ann.type == "length" and "-" in ann.target and ann.label:
        a_name, b_name = ann.target.split("-", 1)
        if a_name in points and b_name in points:
            a = _project(points[a_name])
            b = _project(points[b_name])
            mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            ax.annotate(
                ann.label,
                xy=mid,
                fontsize=10,
                bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.85),
            )
    elif ann.type == "right_angle" and ann.target in points:
        arms = ann.metadata.get("arms") or []
        if len(arms) != 2 or arms[0] not in points or arms[1] not in points:
            return
        v = _project(points[ann.target])
        a = _project(points[arms[0]])
        b = _project(points[arms[1]])
        size = 0.22
        ua = _scaled_unit(v, a, size)
        ub = _scaled_unit(v, b, size)
        if ua is None or ub is None:
            return
        p1 = (v[0] + ua[0], v[1] + ua[1])
        p2 = (p1[0] + ub[0], p1[1] + ub[1])
        p3 = (v[0] + ub[0], v[1] + ub[1])
        ax.plot([p1[0], p2[0], p3[0]], [p1[1], p2[1], p3[1]], color="#e63946", linewidth=1.0)
    elif ann.type == "angle" and ann.target in points and ann.label:
        v = _project(points[ann.target])
        ax.annotate(
            ann.label,
            xy=(v[0] + 0.25, v[1] + 0.25),
            fontsize=9,
            color="#b45309",
        )


def _scaled_unit(
    origin: tuple[float, float], target: tuple[float, float], length: float
) -> tuple[float, float] | None:
    dx, dy = target[0] - origin[0], target[1] - origin[1]
    norm = (dx * dx + dy * dy) ** 0.5
    if norm < 1e-9:
        return None
    return (length * dx / norm, length * dy / norm)


def _build_scene_figure(scene: MathScene, problem_text: str | None = None, response: RenderResponse | None = None) -> plt.Figure:
    scene, hidden_annotations = scene_with_trusted_annotations(scene)
    title = problem_text or scene.problem_text or "Hình"
    notices = export_notice_lines(scene, response, hidden_annotations)
    fig = plt.figure(figsize=(8.27, 11.69), facecolor="white")

    title_ax = fig.add_axes((0.08, 0.82, 0.84, 0.13))
    title_ax.axis("off")
    wrapped = _wrap_text(title, max_chars=90)
    title_ax.text(
        0.0,
        1.0,
        "Đề bài",
        fontsize=11,
        fontweight="bold",
        color="#111111",
        ha="left",
        va="top",
    )
    title_ax.text(
        0.0,
        0.78,
        wrapped,
        fontsize=10,
        color="#0b0c10",
        ha="left",
        va="top",
        wrap=True,
    )
    title_ax.text(
        0.0,
        0.22,
        _wrap_text(" | ".join(notices), max_chars=110),
        fontsize=8.5,
        color="#b45309" if "Hình minh họa" in notices[0] else "#166534",
        ha="left",
        va="top",
        wrap=True,
    )

    figure_ax = fig.add_axes((0.08, 0.08, 0.84, 0.70))
    _draw_scene(scene, figure_ax)
    figure_ax.set_title(scene.topic.replace("_", " ").title(), fontsize=10, color="#525252", loc="left")
    return fig


def build_pdf(scene: MathScene, problem_text: str | None = None, response: RenderResponse | None = None) -> bytes:
    """Trả về bytes của file PDF 1 trang gồm đề bài + hình minh hoạ."""
    buffer = io.BytesIO()
    with PdfPages(buffer) as pdf:
        fig = _build_scene_figure(scene, problem_text, response)
        try:
            pdf.savefig(fig)
        finally:
            plt.close(fig)
    return buffer.getvalue()


def build_png(scene: MathScene, problem_text: str | None = None, response: RenderResponse | None = None) -> bytes:
    buffer = io.BytesIO()
    fig = _build_scene_figure(scene, problem_text, response)
    try:
        fig.savefig(buffer, format="png", dpi=180, bbox_inches="tight", facecolor="white")
    finally:
        plt.close(fig)
    return buffer.getvalue()


def build_jpg(scene: MathScene, problem_text: str | None = None, response: RenderResponse | None = None) -> bytes:
    buffer = io.BytesIO()
    fig = _build_scene_figure(scene, problem_text, response)
    try:
        fig.savefig(buffer, format="jpg", dpi=180, bbox_inches="tight", facecolor="white")
    finally:
        plt.close(fig)
    return buffer.getvalue()


def build_svg(scene: MathScene, problem_text: str | None = None, response: RenderResponse | None = None) -> str:
    buffer = io.StringIO()
    fig = _build_scene_figure(scene, problem_text, response)
    try:
        fig.savefig(buffer, format="svg", bbox_inches="tight", facecolor="white")
    finally:
        plt.close(fig)
    return buffer.getvalue()


def build_pdf_from_capture(scene: MathScene, capture: ExportViewCapture, response: RenderResponse | None = None) -> bytes:
    image_bytes = _decode_capture_data_url(capture)
    image = plt.imread(io.BytesIO(image_bytes))
    _, hidden_annotations = scene_with_trusted_annotations(scene)
    notices = export_notice_lines(scene, response, hidden_annotations)

    buffer = io.BytesIO()
    with PdfPages(buffer) as pdf:
        fig = plt.figure(figsize=(8.27, 11.69), facecolor="white")
        title_ax = fig.add_axes((0.08, 0.84, 0.84, 0.11))
        title_ax.axis("off")
        title_ax.text(0.0, 1.0, "Đề bài", fontsize=11, fontweight="bold", color="#111111", ha="left", va="top")
        title_ax.text(0.0, 0.75, _wrap_text(scene.problem_text or "Hình", 90), fontsize=10, color="#0b0c10", ha="left", va="top", wrap=True)
        title_ax.text(
            0.0,
            0.16,
            _wrap_text(" | ".join([*notices, "Ảnh chụp theo góc nhìn Three.js hiện tại."]), 110),
            fontsize=8.5,
            color="#b45309" if "Hình minh họa" in notices[0] else "#166534",
            ha="left",
            va="top",
            wrap=True,
        )
        image_ax = fig.add_axes((0.06, 0.06, 0.88, 0.74))
        image_ax.imshow(image)
        image_ax.axis("off")
        try:
            pdf.savefig(fig)
        finally:
            plt.close(fig)
    return buffer.getvalue()


def _decode_capture_data_url(capture: ExportViewCapture) -> bytes:
    prefix = f"data:{capture.mime_type};base64,"
    payload = capture.data_url[len(prefix):]
    try:
        data = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("view_capture.data_url không phải base64 hợp lệ.") from error
    if len(data) > 12_000_000:
        raise ValueError("view_capture vượt quá giới hạn 12MB.")
    return data


__all__ = ["build_pdf", "build_pdf_from_capture", "build_png", "build_jpg", "build_svg"]
