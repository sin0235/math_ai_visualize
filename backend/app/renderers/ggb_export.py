"""Xuất MathScene ra file .ggb (zip + XML) cho GeoGebra Classic.

GeoGebra .ggb thực chất là zip chứa ``geogebra.xml`` + ``geogebra_thumbnail.png``
(thumbnail không bắt buộc; GeoGebra mở được file thiếu thumbnail).

Tận dụng ``build_geogebra_commands`` đã có: render thành chuỗi command, sau đó
nhúng vào XML qua ``<construction>`` với mỗi lệnh là một ``<command>`` thay vì
``<expression>``. Cách này đơn giản và đảm bảo GeoGebra parse đúng (giống như
chạy command từ CAS view).

Trả về bytes cho route HTTP set Content-Type ``application/vnd.geogebra.file``.
"""

from __future__ import annotations

import io
import re
import zipfile
from xml.sax.saxutils import escape as xml_escape

from app.renderers.geogebra_commands import build_geogebra_commands
from app.schemas.scene import AdvancedRenderSettings, MathScene

_DEF_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)\s*=\s*(.+)$")


def _categorize_commands(commands: list[str]) -> list[tuple[str, str | None, str]]:
    """Phân loại từng command thành (kind, label, value).

    kind:
    - "def" → label = ... value (ví dụ "A = (1,2)")
    - "cmd" → command thuần như "ShowLabel(A, true)"
    """
    rows: list[tuple[str, str | None, str]] = []
    for raw in commands:
        cmd = raw.strip()
        if not cmd:
            continue
        match = _DEF_RE.match(cmd)
        if match:
            rows.append(("def", match.group(1), match.group(2).strip()))
        else:
            rows.append(("cmd", None, cmd))
    return rows


def _build_xml(scene: MathScene, commands: list[str]) -> str:
    """Sinh geogebra.xml tối thiểu nhưng GeoGebra Classic mở được."""
    is_3d = scene.view.dimension == "3d"
    rows = _categorize_commands(commands)

    construction_parts: list[str] = []
    for kind, label, value in rows:
        if kind == "def":
            # Dùng <command> + <output> để GeoGebra tự đặt label
            label_attr = xml_escape(label or "")
            value_attr = xml_escape(value)
            construction_parts.append(
                f'    <expression label="{label_attr}" exp="{value_attr}"/>'
            )
        else:
            construction_parts.append(f'    <expression exp="{xml_escape(value)}"/>')

    construction = "\n".join(construction_parts)

    # View 3D vs 2D quyết định perspective
    perspective = "T" if is_3d else "G"  # T = Geometry 3D layout, G = Graphing

    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<geogebra format="5.0" version="5.0.832.0" app="classic" platform="w" id="hinh-export">
  <gui>
    <window width="1024" height="768"/>
    <perspectives>
      <perspective id="tmp">
        <panes>
          <pane location="" divider="0.7" orientation="1"/>
        </panes>
        <views>
          <view id="1" toolbar="0 || 1 501 5 19 , 67 , 72 || 2 15 45 18 , 7 37 || 4 3 8 9 , 13 44 , 58 , 47" visible="true" inframe="false" stylebar="false" location="1" size="600" window="100,100,600,600"/>
          <view id="512" visible="{str(is_3d).lower()}" inframe="false" stylebar="false" location="3" size="600" window="100,100,600,600"/>
        </views>
        <toolbar show="true" items="0 39 59 || 1 501 5 19 , 67 , 72 || 2 15 45 18 , 7 37"/>
        <input show="true" cmd="true" top="algebra"/>
      </perspective>
    </perspectives>
    <labelingStyle val="3"/>
    <font size="16"/>
  </gui>
  <euclidianView>
    <viewNumber viewNo="1"/>
    <coordSystem xZero="215" yZero="315" scale="50" yscale="50"/>
    <evSettings axes="true" grid="true" gridIsBold="false" pointCapturing="3"/>
    <bgColor r="255" g="255" b="255"/>
    <axesColor r="0" g="0" b="0"/>
    <gridColor r="192" g="192" b="192"/>
    <lineStyle axes="1" grid="0"/>
    <axis id="0" show="true" label="x" unitLabel="" tickStyle="1" showNumbers="true"/>
    <axis id="1" show="true" label="y" unitLabel="" tickStyle="1" showNumbers="true"/>
  </euclidianView>
  <kernel>
    <continuous val="false"/>
    <decimals val="2"/>
    <angleUnit val="degree"/>
    <algebraStyle val="3" spreadsheet="0"/>
    <coordStyle val="0"/>
  </kernel>
  <construction title="{xml_escape(scene.problem_text[:120])}" author="" date="">
{construction}
  </construction>
</geogebra>
"""
    return xml


def build_ggb(
    scene: MathScene, settings: AdvancedRenderSettings | None = None
) -> bytes:
    """Trả về nội dung file .ggb (zip)."""
    commands = build_geogebra_commands(scene, settings or AdvancedRenderSettings())
    xml = _build_xml(scene, commands)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("geogebra.xml", xml)
    return buffer.getvalue()


__all__ = ["build_ggb"]
