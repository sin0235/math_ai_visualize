import io
import zipfile

import pytest
from pydantic import ValidationError

from app.renderers.ggb_export import build_ggb
from app.renderers.katex_html_export import build_katex_html
from app.renderers.pdf_export import build_jpg, build_pdf, build_pdf_from_capture, build_png, build_svg
from app.renderers.tikz_export import build_tikz, build_tikz_document
from app.schemas.scene import ExportViewCapture, MathScene, SceneRenderRequest


def _scene_2d() -> MathScene:
    return MathScene.model_validate(
        {
            "problem_text": "Tam giác ABC đều cạnh 4",
            "renderer": "geogebra_2d",
            "topic": "coordinate_2d",
            "view": {"dimension": "2d"},
            "objects": [
                {"type": "point_2d", "name": "A", "x": 0, "y": 0},
                {"type": "point_2d", "name": "B", "x": 4, "y": 0},
                {"type": "point_2d", "name": "C", "x": 2, "y": 3.464},
                {"type": "segment", "points": ["A", "B"]},
                {"type": "segment", "points": ["B", "C"]},
                {"type": "segment", "points": ["C", "A"]},
            ],
            "annotations": [
                {"type": "length", "target": "A-B", "label": "4", "metadata": {}},
            ],
        }
    )


def _scene_3d() -> MathScene:
    return MathScene.model_validate(
        {
            "problem_text": "Hình chóp S.ABCD đáy vuông",
            "renderer": "threejs_3d",
            "topic": "solid_geometry",
            "view": {"dimension": "3d"},
            "objects": [
                {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
                {"type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
                {"type": "point_3d", "name": "C", "x": 4, "y": 0, "z": 4},
                {"type": "point_3d", "name": "D", "x": 0, "y": 0, "z": 4},
                {"type": "point_3d", "name": "S", "x": 0, "y": 3, "z": 0},
                {"type": "face", "name": "ABCD", "points": ["A", "B", "C", "D"]},
                {"type": "segment", "points": ["S", "A"]},
                {"type": "segment", "points": ["S", "B"]},
                {"type": "segment", "points": ["S", "C"]},
                {"type": "segment", "points": ["S", "D"]},
            ],
            "annotations": [
                {
                    "type": "right_angle",
                    "target": "A",
                    "metadata": {"arms": ["B", "S"]},
                },
            ],
        }
    )


def test_tikz_2d_contains_expected_primitives():
    tikz = build_tikz(_scene_2d())
    assert "\\begin{tikzpicture}" in tikz
    assert "(0,0)" in tikz
    assert "(4,0)" in tikz
    assert "$A$" in tikz and "$B$" in tikz and "$C$" in tikz
    assert "\\draw" in tikz
    assert "\\end{tikzpicture}" in tikz


def test_tikz_3d_uses_oblique_projection():
    scene = _scene_3d()
    tikz = build_tikz(scene)
    assert "\\begin{tikzpicture}" in tikz
    assert "$S$" in tikz
    # S(0, 3, 0) → projection: x=0+0.5*3*cos(30)≈1.299, y=0+0.5*3*sin(30)=0.75
    assert "1.299" in tikz or "1.3" in tikz
    assert "0.75" in tikz


def test_tikz_document_is_compilable_string():
    doc = build_tikz_document(_scene_2d())
    assert "\\documentclass" in doc
    assert "\\begin{document}" in doc
    assert "\\end{document}" in doc
    assert "\\begin{tikzpicture}" in doc


def test_ggb_is_valid_zip_with_xml():
    ggb_bytes = build_ggb(_scene_2d())
    assert ggb_bytes.startswith(b"PK")  # ZIP signature
    with zipfile.ZipFile(io.BytesIO(ggb_bytes)) as zf:
        names = zf.namelist()
        assert "geogebra.xml" in names
        xml = zf.read("geogebra.xml").decode("utf-8")
    assert "<geogebra" in xml
    assert "<construction" in xml
    # Có ít nhất 3 expression cho 3 điểm
    assert xml.count("<expression") >= 3


def test_pdf_export_returns_pdf_bytes():
    pdf_bytes = build_pdf(_scene_2d())
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 1000


def test_pdf_export_from_current_view_capture_returns_pdf_bytes():
    capture = ExportViewCapture(
        mime_type="image/png",
        data_url="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=",
        width=16,
        height=16,
    )

    pdf_bytes = build_pdf_from_capture(_scene_3d(), capture)

    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 1000


def test_scene_render_request_rejects_mismatched_view_capture_mime():
    with pytest.raises(ValidationError):
        SceneRenderRequest.model_validate(
            {
                "scene": _scene_2d().model_dump(),
                "view_capture": {
                    "mime_type": "image/png",
                    "data_url": "data:image/jpeg;base64,AAAA",
                    "width": 16,
                    "height": 16,
                },
            }
        )


def test_png_export_returns_png_bytes():
    png_bytes = build_png(_scene_2d())
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(png_bytes) > 1000


def test_jpg_export_returns_jpeg_bytes():
    jpg_bytes = build_jpg(_scene_2d())
    assert jpg_bytes.startswith(b"\xff\xd8")
    assert len(jpg_bytes) > 1000


def test_svg_export_returns_svg_text():
    svg = build_svg(_scene_2d())
    assert "<svg" in svg
    assert "</svg>" in svg


def test_katex_html_export_contains_katex_assets():
    html = build_katex_html(_scene_2d())
    assert "<html" in html
    assert "katex.min.css" in html
    assert "renderMathInElement" in html
    assert "Tam giác ABC" in html


def test_export_filters_untrusted_measurement_labels_and_keeps_warning():
    scene = MathScene.model_validate(
        {
            "problem_text": "Tam giác ABC",
            "renderer": "geogebra_2d",
            "topic": "coordinate_2d",
            "view": {"dimension": "2d"},
            "objects": [
                {"type": "point_2d", "name": "A", "x": 0, "y": 0},
                {"type": "point_2d", "name": "B", "x": 1, "y": 0},
                {"type": "segment", "points": ["A", "B"]},
            ],
            "interpretation": {"assumptions": ["B chọn để minh họa"], "missing_data": []},
            "annotations": [
                {"type": "length", "target": "A-B", "label": "99", "metadata": {"source": "construction", "confidence": "unverified"}},
            ],
        }
    )

    tikz = build_tikz_document(scene)
    html = build_katex_html(scene)
    ggb_bytes = build_ggb(scene)

    assert "Hình minh họa" in tikz
    assert "99" not in tikz
    assert "Hình minh họa" in html
    assert "99" not in html
    with zipfile.ZipFile(io.BytesIO(ggb_bytes)) as zf:
        xml = zf.read("geogebra.xml").decode("utf-8")
    assert "Hình minh họa" in xml
    assert "99" not in xml
