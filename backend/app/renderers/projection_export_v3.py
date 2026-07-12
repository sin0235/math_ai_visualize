from __future__ import annotations

import base64
import binascii
import io
import zipfile
from html import escape
from math import cos, pi, sin

import matplotlib

matplotlib.use("Agg")

import matplotlib.patches as mpatches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

from app.renderers.geogebra_commands import build_geogebra_commands_v3
from app.schemas.render_projection_v3 import Position3, RenderProjectionV3
from app.schemas.scene import ExportViewCapture


def build_tikz_document_v3(projection: RenderProjectionV3, problem_text: str) -> str:
    body = build_tikz_v3(projection)
    title = problem_text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
    return (
        "\\documentclass[border=10pt]{standalone}\n"
        "\\usepackage{tikz}\n\\usepackage{xcolor}\n"
        "\\usepackage[utf8]{inputenc}\n\\usepackage[T5]{fontenc}\n"
        "\\begin{document}\n"
        f"% {title}\n{body}\n"
        "\\end{document}\n"
    )


def build_tikz_v3(projection: RenderProjectionV3) -> str:
    lines = ["\\begin{tikzpicture}[scale=1.0,every node/.style={font=\\small}]"]
    for surface in projection.surfaces:
        if surface.kind == "face" and surface.visible:
            coords = " -- ".join(_tikz_coord(_project(position, projection.dimension)) for position in surface.positions)
            lines.append(f"  \\fill[fill opacity={surface.opacity:.2f},draw=none] {coords} -- cycle;")
    for item in projection.linear:
        if not item.visible:
            continue
        start, end = (_project(position, projection.dimension) for position in item.positions)
        style = "dashed" if item.style in {"dashed", "dotted"} else "solid"
        arrow = "->," if item.kind == "vector" else ""
        lines.append(f"  \\draw[{arrow}thick,{style}] {_tikz_coord(start)} -- {_tikz_coord(end)};")
    for circle in projection.circles:
        if circle.visible:
            lines.append(
                f"  \\draw[thick] {_tikz_coord(_project(circle.center, projection.dimension))} circle ({_fmt(circle.radius)});"
            )
    for sphere in projection.spheres:
        if sphere.visible:
            lines.append(
                f"  \\draw[thick] {_tikz_coord(_project(sphere.center, projection.dimension))} circle ({_fmt(sphere.radius)});"
            )
    for point in projection.points:
        if point.visible:
            label = _escape_latex(point.label or point.name)
            lines.append(
                f"  \\fill {_tikz_coord(_project(point.position, projection.dimension))} circle (1.5pt) node[above right] {{${label}$}};"
            )
    lines.extend(_tikz_annotations(projection))
    lines.append("\\end{tikzpicture}")
    return "\n".join(lines)


def build_ggb_v3(projection: RenderProjectionV3, problem_text: str) -> bytes:
    expressions = []
    for command in build_geogebra_commands_v3(projection):
        expressions.append(f'    <expression exp="{escape(command)}"/>')
    xml = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<geogebra format="5.0" version="5.0.832.0" app="classic" platform="w" id="hinh-export-v3">\n'
        f'  <construction title="{escape(problem_text[:120])}" author="" date="">\n'
        + "\n".join(expressions)
        + "\n  </construction>\n</geogebra>\n"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("geogebra.xml", xml)
    return buffer.getvalue()


def build_pdf_v3(
    projection: RenderProjectionV3,
    problem_text: str,
    capture: ExportViewCapture | None = None,
) -> bytes:
    buffer = io.BytesIO()
    with PdfPages(buffer) as pdf:
        figure = _capture_figure(projection, problem_text, capture) if capture else _projection_figure(projection, problem_text)
        try:
            pdf.savefig(figure)
        finally:
            plt.close(figure)
    return buffer.getvalue()


def build_image_v3(projection: RenderProjectionV3, problem_text: str, image_format: str) -> bytes | str:
    binary = image_format != "svg"
    buffer = io.BytesIO() if binary else io.StringIO()
    figure = _projection_figure(projection, problem_text)
    try:
        figure.savefig(buffer, format=image_format, dpi=180, bbox_inches="tight", facecolor="white")
    finally:
        plt.close(figure)
    return buffer.getvalue()


def build_katex_html_v3(projection: RenderProjectionV3, problem_text: str) -> str:
    title = escape(problem_text or "Hình")
    tikz = escape(build_tikz_v3(projection))
    return f"""<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css" />
  <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
  <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js" onload="renderMathInElement(document.body);"></script>
</head>
<body>
  <main><h1>Đề bài</h1><p>{title}</p><p>Scene {escape(projection.scene_id)}, revision {projection.revision}</p><pre>{tikz}</pre></main>
</body>
</html>
"""


def _projection_figure(projection: RenderProjectionV3, problem_text: str):
    figure = plt.figure(figsize=(8.27, 11.69), facecolor="white")
    title_ax = figure.add_axes((0.08, 0.84, 0.84, 0.11))
    title_ax.axis("off")
    title_ax.text(0, 1, "Đề bài", fontsize=11, fontweight="bold", va="top")
    title_ax.text(0, 0.72, _wrap_text(problem_text), fontsize=10, va="top", wrap=True)
    title_ax.text(0, 0.1, f"Scene v3 committed · revision {projection.revision}", fontsize=8.5, color="#166534")
    axes = figure.add_axes((0.08, 0.08, 0.84, 0.70))
    _draw_projection(projection, axes)
    return figure


def _capture_figure(projection: RenderProjectionV3, problem_text: str, capture: ExportViewCapture):
    image = plt.imread(io.BytesIO(_decode_capture(capture)))
    figure = plt.figure(figsize=(8.27, 11.69), facecolor="white")
    title_ax = figure.add_axes((0.08, 0.84, 0.84, 0.11))
    title_ax.axis("off")
    title_ax.text(0, 1, "Đề bài", fontsize=11, fontweight="bold", va="top")
    title_ax.text(0, 0.72, _wrap_text(problem_text), fontsize=10, va="top", wrap=True)
    title_ax.text(0, 0.1, f"Scene v3 committed · revision {projection.revision} · góc nhìn hiện tại", fontsize=8.5, color="#166534")
    image_ax = figure.add_axes((0.06, 0.06, 0.88, 0.74))
    image_ax.imshow(image)
    image_ax.axis("off")
    return figure


def _draw_projection(projection: RenderProjectionV3, axes) -> None:
    for surface in projection.surfaces:
        if surface.kind == "face" and surface.visible:
            positions = [_project(position, projection.dimension) for position in surface.positions]
            axes.add_patch(mpatches.Polygon(positions, closed=True, facecolor=surface.color, edgecolor="none", alpha=surface.opacity))
    for item in projection.linear:
        if not item.visible:
            continue
        start, end = (_project(position, projection.dimension) for position in item.positions)
        if item.kind == "vector":
            axes.annotate("", xy=end, xytext=start, arrowprops={"arrowstyle": "->", "color": item.color or "#7c3aed", "lw": item.line_width or 1.6})
        else:
            axes.plot(
                [start[0], end[0]],
                [start[1], end[1]],
                color=item.color or "#1d3557",
                linewidth=item.line_width or 1.6,
                linestyle="--" if item.style in {"dashed", "dotted"} else "-",
            )
    for circle in projection.circles:
        if circle.visible:
            axes.add_patch(mpatches.Circle(_project(circle.center, projection.dimension), circle.radius, fill=False, color="#1d3557"))
    for sphere in projection.spheres:
        if sphere.visible:
            axes.add_patch(mpatches.Circle(_project(sphere.center, projection.dimension), sphere.radius, fill=False, color=sphere.color, alpha=sphere.opacity))
    for point in projection.points:
        if not point.visible:
            continue
        x, y = _project(point.position, projection.dimension)
        axes.plot(x, y, "o", color="#0b0c10", markersize=4)
        axes.annotate(point.label or point.name, (x, y), xytext=(6, 6), textcoords="offset points", fontweight="bold")
    axes.set_aspect("equal", adjustable="datalim")
    axes.grid(projection.view.show_grid, linestyle=":", alpha=0.3)
    if projection.view.show_axes:
        axes.axhline(0, color="#999", linewidth=0.5)
        axes.axvline(0, color="#999", linewidth=0.5)


def _tikz_annotations(projection: RenderProjectionV3) -> list[str]:
    points = {point.object_id: _project(point.position, projection.dimension) for point in projection.points}
    lines: list[str] = []
    for annotation in projection.annotations:
        if annotation.type == "length" and annotation.label and len(annotation.target_ids) >= 2:
            first, second = (points.get(target_id) for target_id in annotation.target_ids[:2])
            if first is not None and second is not None:
                midpoint = ((first[0] + second[0]) / 2, (first[1] + second[1]) / 2)
                lines.append(f"  \\node[fill=white,inner sep=1pt] at {_tikz_coord(midpoint)} {{${_escape_latex(annotation.label)}$}};")
    return lines


def _project(position: Position3, dimension: str) -> tuple[float, float]:
    x, y, z = position
    if dimension == "2d":
        return x, y
    angle = pi / 6
    return x + 0.5 * y * cos(angle), z + 0.5 * y * sin(angle)


def _decode_capture(capture: ExportViewCapture) -> bytes:
    payload = capture.data_url.split(",", 1)[1]
    try:
        data = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("view_capture.data_url không phải base64 hợp lệ.") from error
    if len(data) > 12_000_000:
        raise ValueError("view_capture vượt quá giới hạn 12MB.")
    return data


def _wrap_text(text: str, width: int = 90) -> str:
    words, lines, line = text.split(), [], ""
    for word in words:
        if len(line) + len(word) + 1 > width:
            lines.append(line.rstrip())
            line = ""
        line += word + " "
    if line:
        lines.append(line.rstrip())
    return "\n".join(lines)


def _fmt(value: float) -> str:
    return str(int(round(value))) if abs(value - round(value)) < 1e-6 else f"{value:.3f}".rstrip("0").rstrip(".")


def _tikz_coord(position: tuple[float, float]) -> str:
    return f"({_fmt(position[0])},{_fmt(position[1])})"


def _escape_latex(value: str) -> str:
    return value.replace("°", "^{\\circ}").replace("&", "\\&")


__all__ = [
    "build_ggb_v3",
    "build_image_v3",
    "build_katex_html_v3",
    "build_pdf_v3",
    "build_tikz_document_v3",
    "build_tikz_v3",
]