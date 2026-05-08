import io
import zipfile

from app.renderers.ggb_export import build_ggb
from app.renderers.tikz_export import build_tikz, build_tikz_document
from app.schemas.scene import MathScene


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
    from app.renderers.pdf_export import build_pdf

    pdf_bytes = build_pdf(_scene_2d())
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 1000
