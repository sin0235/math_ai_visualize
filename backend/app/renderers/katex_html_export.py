from __future__ import annotations

from html import escape

from app.renderers.tikz_export import build_tikz
from app.schemas.scene import Annotation, Face, Line2D, Line3D, MathScene, Point2D, Point3D, Segment, Vector2D, Vector3D, RenderResponse
from app.services.scene_trust import export_notice_lines, scene_with_trusted_annotations


def build_katex_html(scene: MathScene, response: RenderResponse | None = None) -> str:
    scene, hidden_annotations = scene_with_trusted_annotations(scene)
    title = escape(scene.problem_text or "Hình")
    topic = escape(scene.topic.replace("_", " ").title())
    renderer = escape(scene.renderer)
    notices = "".join(f"<li>{escape(line)}</li>" for line in export_notice_lines(scene, response, hidden_annotations))
    objects = "\n".join(_object_item(obj) for obj in scene.objects)
    annotations = "\n".join(_annotation_item(annotation) for annotation in scene.annotations)
    tikz = escape(build_tikz(scene))

    return f"""<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css" />
  <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
  <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js" onload="renderMathInElement(document.body, {{ delimiters: [{{left: '$$', right: '$$', display: true}}, {{left: '\\\\[', right: '\\\\]', display: true}}, {{left: '\\\\(', right: '\\\\)', display: false}}] }});"></script>
  <style>
    :root {{ color: #111111; background: #f5f5f5; font-family: 'Times New Roman', serif; }}
    body {{ margin: 0; padding: 32px; }}
    main {{ max-width: 900px; margin: 0 auto; background: #ffffff; border: 1px solid #d4d4d4; border-radius: 18px; padding: 28px; }}
    h1, h2 {{ margin: 0 0 12px; }}
    h1 {{ font-size: 1.5rem; }}
    h2 {{ font-size: 1rem; margin-top: 24px; }}
    p {{ line-height: 1.55; }}
    ul {{ padding-left: 22px; }}
    li {{ margin: 4px 0; }}
    pre {{ white-space: pre-wrap; overflow: auto; border: 1px solid #d4d4d4; border-radius: 12px; padding: 14px; background: #fafafa; }}
    .meta {{ color: #525252; font-size: 0.9rem; }}
    .warning {{ border: 1px solid #f59e0b; background: #fffbeb; border-radius: 12px; padding: 12px 16px; color: #92400e; }}
  </style>
</head>
<body>
  <main>
    <h1>Đề bài</h1>
    <p>{title}</p>
    <p class="meta">Loại: {topic} · Renderer: {renderer}</p>
    <section class="warning" aria-label="Cảnh báo dựng hình"><strong>Trạng thái hình</strong><ul>{notices}</ul></section>
    <h2>Đối tượng hình học</h2>
    <ul>{objects or '<li>Không có đối tượng.</li>'}</ul>
    <h2>Ghi chú</h2>
    <ul>{annotations or '<li>Không có ghi chú.</li>'}</ul>
    <h2>TikZ source</h2>
    <pre>{tikz}</pre>
  </main>
</body>
</html>
"""


def _object_item(obj: object) -> str:
    if isinstance(obj, (Point2D, Point3D)):
        coords = f"({obj.x:g}; {obj.y:g}" + (f"; {obj.z:g}" if isinstance(obj, Point3D) else "") + ")"
        return f"<li>Điểm <strong>{escape(obj.name)}</strong>: {escape(coords)}</li>"
    if isinstance(obj, Segment):
        return f"<li>Đoạn thẳng {escape(''.join(obj.points))}</li>"
    if isinstance(obj, (Line2D, Line3D)):
        name = obj.name or ""
        return f"<li>Đường thẳng {escape(name)} qua {escape(' và '.join(obj.through))}</li>"
    if isinstance(obj, (Vector2D, Vector3D)):
        name = obj.name or ""
        return f"<li>Vector {escape(name)}: {escape(obj.from_point)} → {escape(obj.to_point)}</li>"
    if isinstance(obj, Face):
        name = obj.name or ""
        return f"<li>Mặt {escape(name)}: {escape(', '.join(obj.points))}</li>"
    type_name = getattr(obj, "type", obj.__class__.__name__)
    return f"<li>{escape(str(type_name))}</li>"


def _annotation_item(annotation: Annotation) -> str:
    label = f": {escape(annotation.label)}" if annotation.label else ""
    return f"<li>{escape(annotation.type)} tại {escape(annotation.target)}{label}</li>"


__all__ = ["build_katex_html"]
