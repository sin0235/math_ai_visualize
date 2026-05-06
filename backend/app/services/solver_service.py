"""
Geometry Step-by-Step Solver (Lựa chọn 2).

Nhận scene JSON + câu hỏi → dùng SymPy tính toán chính xác → LLM diễn giải từng bước.
Output: list[SolverStep] với highlight objects tương ứng trên 3D viewer.
"""
from __future__ import annotations

import re
from math import acos, degrees, sqrt
from typing import Any

from sympy import (
    Abs, Matrix, N, Rational, S, acos as sym_acos, cos, pi, simplify, sqrt as sym_sqrt, symbols
)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class SolverStep:
    def __init__(
        self,
        index: int,
        title: str,
        explanation: str,
        expression: str | None,
        result: str | None,
        highlight: list[str],
    ) -> None:
        self.index = index
        self.title = title
        self.explanation = explanation
        self.expression = expression
        self.result = result
        self.highlight = highlight  # list of point/segment/face names to highlight

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "title": self.title,
            "explanation": self.explanation,
            "expression": self.expression,
            "result": self.result,
            "highlight": self.highlight,
        }


class SolverResult:
    def __init__(self, question: str, answer: str, steps: list[SolverStep], warnings: list[str]) -> None:
        self.question = question
        self.answer = answer
        self.steps = steps
        self.warnings = warnings

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "steps": [s.to_dict() for s in self.steps],
            "warnings": self.warnings,
        }


# ---------------------------------------------------------------------------
# Vector helpers (Python floats, bypass SymPy for speed)
# ---------------------------------------------------------------------------

Vec3 = tuple[float, float, float]

def _v(x: float, y: float, z: float) -> Vec3:
    return (x, y, z)

def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0]-b[0], a[1]-b[1], a[2]-b[2])

def _dot(a: Vec3, b: Vec3) -> float:
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]

def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])

def _norm(a: Vec3) -> float:
    return sqrt(_dot(a, a))

def _normalize(a: Vec3) -> Vec3:
    n = _norm(a)
    if n < 1e-12:
        return (0.0, 0.0, 0.0)
    return (a[0]/n, a[1]/n, a[2]/n)

def _fmt(v: float, digits: int = 4) -> str:
    """Format a float nicely – avoid trailing zeros."""
    s = f"{v:.{digits}f}".rstrip("0").rstrip(".")
    return s or "0"


# ---------------------------------------------------------------------------
# Scene helpers
# ---------------------------------------------------------------------------

def _point_map(scene_dict: dict) -> dict[str, Vec3]:
    pts: dict[str, Vec3] = {}
    for obj in scene_dict.get("objects", []):
        if obj.get("type") == "point_3d":
            pts[obj["name"]] = _v(float(obj["x"]), float(obj["y"]), float(obj["z"]))
    return pts

def _parse_edge(token: str) -> tuple[str, str] | None:
    """Parse 'AB' or 'A-B' → ('A','B')."""
    token = token.strip()
    if "-" in token:
        parts = token.split("-")
        if len(parts) == 2 and all(p.strip() for p in parts):
            return parts[0].strip(), parts[1].strip()
    if len(token) == 2 and token.isalpha():
        return token[0], token[1]
    return None

def _plane_normal(pts_list: list[Vec3]) -> Vec3 | None:
    if len(pts_list) < 3:
        return None
    for i in range(len(pts_list)-2):
        v1 = _sub(pts_list[i+1], pts_list[i])
        v2 = _sub(pts_list[i+2], pts_list[i])
        n = _cross(v1, v2)
        if _norm(n) > 1e-9:
            return _normalize(n)
    return None

def _face_normal(face_name: str, scene_dict: dict, pts: dict[str, Vec3]) -> Vec3 | None:
    for obj in scene_dict.get("objects", []):
        if obj.get("type") == "face" and obj.get("name") == face_name:
            face_pts = [pts[p] for p in obj["points"] if p in pts]
            return _plane_normal(face_pts)
    return None


# ---------------------------------------------------------------------------
# Core solver: detect question type → dispatch
# ---------------------------------------------------------------------------

_DISTANCE_RE = re.compile(
    r"kho[aả]ng\s*c[áa]ch|distance|d\(|d\s*\(", re.IGNORECASE
)
_ANGLE_RE = re.compile(
    r"g[oó]c|angle|cos\s*\(|sin\s*\(", re.IGNORECASE
)
_AREA_RE = re.compile(
    r"di[eệ]n\s*t[íi]ch|area", re.IGNORECASE
)
_VOLUME_RE = re.compile(
    r"th[eể]\s*t[íi]ch|volume", re.IGNORECASE
)
_PARALLEL_RE = re.compile(
    r"song\s*song|parallel", re.IGNORECASE
)
_PERP_RE = re.compile(
    r"vu[oô]ng\s*g[oó]c|perpendicular", re.IGNORECASE
)


def solve(scene_dict: dict, question: str) -> SolverResult:
    """Main entry point. Returns SolverResult with steps."""
    pts = _point_map(scene_dict)
    warnings: list[str] = []

    q = question.strip()

    if _DISTANCE_RE.search(q):
        return _solve_distance(scene_dict, pts, q, warnings)
    if _ANGLE_RE.search(q):
        return _solve_angle(scene_dict, pts, q, warnings)
    if _AREA_RE.search(q):
        return _solve_area(scene_dict, pts, q, warnings)
    if _VOLUME_RE.search(q):
        return _solve_volume(scene_dict, pts, q, warnings)
    if _PARALLEL_RE.search(q):
        return _solve_parallel(scene_dict, pts, q, warnings)
    if _PERP_RE.search(q):
        return _solve_perpendicular(scene_dict, pts, q, warnings)

    warnings.append("Chưa nhận diện được dạng bài. Hãy thử hỏi cụ thể hơn (khoảng cách, góc, diện tích, thể tích, song song, vuông góc).")
    return SolverResult(q, "Không xác định", [], warnings)


# ---------------------------------------------------------------------------
# Distance solver
# ---------------------------------------------------------------------------

def _solve_distance(scene_dict: dict, pts: dict[str, Vec3], question: str, warnings: list[str]) -> SolverResult:
    steps: list[SolverStep] = []

    # Extract two uppercase point names from question
    point_names = re.findall(r'\b([A-Z][0-9\']*)\b', question)
    # Also try edge token like AB
    edge_tokens = re.findall(r'\b([A-Z][0-9\']*[A-Z][0-9\']*)\b', question)

    if len(point_names) >= 2:
        p_name, q_name = point_names[0], point_names[1]
    elif edge_tokens:
        token = edge_tokens[0]
        p_name, q_name = token[0], token[1]
    else:
        warnings.append("Không tìm được hai điểm trong câu hỏi.")
        return SolverResult(question, "Không xác định", [], warnings)

    if p_name not in pts:
        warnings.append(f"Điểm {p_name} không có trong scene.")
        return SolverResult(question, "Không xác định", steps, warnings)
    if q_name not in pts:
        warnings.append(f"Điểm {q_name} không có trong scene.")
        return SolverResult(question, "Không xác định", steps, warnings)

    P = pts[p_name]
    Q = pts[q_name]

    steps.append(SolverStep(
        index=1,
        title=f"Xác định toạ độ {p_name} và {q_name}",
        explanation=f"Từ scene, ta có: {p_name}({_fmt(P[0])}, {_fmt(P[1])}, {_fmt(P[2])}) và {q_name}({_fmt(Q[0])}, {_fmt(Q[1])}, {_fmt(Q[2])}).",
        expression=None,
        result=None,
        highlight=[p_name, q_name],
    ))

    diff = _sub(Q, P)
    steps.append(SolverStep(
        index=2,
        title=f"Tính vector {p_name}{q_name}",
        explanation=f"Vector {p_name}{q_name} = {q_name} - {p_name} = ({_fmt(diff[0])}, {_fmt(diff[1])}, {_fmt(diff[2])}).",
        expression=f"→{p_name}{q_name} = ({_fmt(diff[0])}, {_fmt(diff[1])}, {_fmt(diff[2])})",
        result=None,
        highlight=[p_name, q_name],
    ))

    dist = _norm(diff)
    sq_terms = f"{_fmt(diff[0])}² + {_fmt(diff[1])}² + {_fmt(diff[2])}²"
    steps.append(SolverStep(
        index=3,
        title=f"Tính khoảng cách {p_name}{q_name}",
        explanation=f"|{p_name}{q_name}| = √({sq_terms}) = {_fmt(dist, 6)}",
        expression=f"|{p_name}{q_name}| = √({sq_terms})",
        result=_fmt(dist, 6),
        highlight=[p_name, q_name],
    ))

    return SolverResult(
        question=question,
        answer=f"|{p_name}{q_name}| = {_fmt(dist, 6)}",
        steps=steps,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Angle solver
# ---------------------------------------------------------------------------

def _solve_angle(scene_dict: dict, pts: dict[str, Vec3], question: str, warnings: list[str]) -> SolverResult:
    steps: list[SolverStep] = []
    point_names = re.findall(r'\b([A-Z][0-9\']*)\b', question)

    if len(point_names) < 3:
        warnings.append("Góc cần ít nhất 3 điểm (ví dụ: góc ABC).")
        return SolverResult(question, "Không xác định", steps, warnings)

    A_name, B_name, C_name = point_names[0], point_names[1], point_names[2]
    for name in (A_name, B_name, C_name):
        if name not in pts:
            warnings.append(f"Điểm {name} không có trong scene.")
            return SolverResult(question, "Không xác định", steps, warnings)

    A, B, C = pts[A_name], pts[B_name], pts[C_name]

    steps.append(SolverStep(
        index=1,
        title=f"Xác định toạ độ {A_name}, {B_name}, {C_name}",
        explanation=f"{A_name}({_fmt(A[0])}, {_fmt(A[1])}, {_fmt(A[2])}), {B_name}({_fmt(B[0])}, {_fmt(B[1])}, {_fmt(B[2])}), {C_name}({_fmt(C[0])}, {_fmt(C[1])}, {_fmt(C[2])}).",
        expression=None,
        result=None,
        highlight=[A_name, B_name, C_name],
    ))

    BA = _sub(A, B)
    BC = _sub(C, B)
    steps.append(SolverStep(
        index=2,
        title=f"Tính vector {B_name}{A_name} và {B_name}{C_name}",
        explanation=f"→{B_name}{A_name} = ({_fmt(BA[0])}, {_fmt(BA[1])}, {_fmt(BA[2])})\n→{B_name}{C_name} = ({_fmt(BC[0])}, {_fmt(BC[1])}, {_fmt(BC[2])})",
        expression=None,
        result=None,
        highlight=[A_name, B_name, C_name],
    ))

    dot = _dot(BA, BC)
    norm_ba = _norm(BA)
    norm_bc = _norm(BC)
    if norm_ba < 1e-12 or norm_bc < 1e-12:
        warnings.append("Một trong hai vector có độ dài bằng 0.")
        return SolverResult(question, "Không xác định", steps, warnings)

    cos_val = max(-1.0, min(1.0, dot / (norm_ba * norm_bc)))
    angle_rad = acos(cos_val)
    angle_deg = degrees(angle_rad)

    steps.append(SolverStep(
        index=3,
        title=f"Tính cos(∠{A_name}{B_name}{C_name})",
        explanation=f"cos(∠{A_name}{B_name}{C_name}) = (→{B_name}{A_name} · →{B_name}{C_name}) / (|{B_name}{A_name}| × |{B_name}{C_name}|)",
        expression=f"cos = {_fmt(dot)} / ({_fmt(norm_ba)} × {_fmt(norm_bc)}) = {_fmt(cos_val, 6)}",
        result=_fmt(cos_val, 6),
        highlight=[A_name, B_name, C_name],
    ))

    steps.append(SolverStep(
        index=4,
        title=f"Kết quả góc ∠{A_name}{B_name}{C_name}",
        explanation=f"∠{A_name}{B_name}{C_name} = arccos({_fmt(cos_val, 4)}) ≈ {_fmt(angle_deg, 2)}°",
        expression=f"∠{A_name}{B_name}{C_name} = arccos({_fmt(cos_val, 4)})",
        result=f"≈ {_fmt(angle_deg, 2)}°",
        highlight=[A_name, B_name, C_name],
    ))

    return SolverResult(
        question=question,
        answer=f"∠{A_name}{B_name}{C_name} ≈ {_fmt(angle_deg, 2)}°",
        steps=steps,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Area solver (triangle from 3 points extracted from question or face)
# ---------------------------------------------------------------------------

def _solve_area(scene_dict: dict, pts: dict[str, Vec3], question: str, warnings: list[str]) -> SolverResult:
    steps: list[SolverStep] = []
    point_names = re.findall(r'\b([A-Z][0-9\']*)\b', question)

    # Try to find a face matching point sequence
    face_obj = None
    for obj in scene_dict.get("objects", []):
        if obj.get("type") != "face":
            continue
        face_pts_names: list[str] = obj.get("points", [])
        if any(p in point_names for p in face_pts_names):
            face_obj = obj
            break

    if face_obj:
        fp_names: list[str] = face_obj["points"]
        face_pts_3d = [pts[n] for n in fp_names if n in pts]
        if len(face_pts_3d) < 3:
            warnings.append("Mặt không đủ điểm để tính diện tích.")
            return SolverResult(question, "Không xác định", steps, warnings)

        n_name = fp_names[0] if len(fp_names) > 0 else "A"
        steps.append(SolverStep(
            index=1,
            title=f"Xác định mặt {face_obj.get('name', '')} và các đỉnh",
            explanation=f"Mặt có các đỉnh: {', '.join(fp_names)}.",
            expression=None,
            result=None,
            highlight=fp_names,
        ))

        # Triangulate polygon
        total_area = 0.0
        area_details: list[str] = []
        anchor = face_pts_3d[0]
        for i in range(1, len(face_pts_3d)-1):
            v1 = _sub(face_pts_3d[i], anchor)
            v2 = _sub(face_pts_3d[i+1], anchor)
            cross = _cross(v1, v2)
            tri_area = _norm(cross) / 2
            total_area += tri_area
            area_details.append(f"△{fp_names[0]}{fp_names[i]}{fp_names[i+1]} = {_fmt(tri_area, 4)}")

        steps.append(SolverStep(
            index=2,
            title="Chia thành tam giác và tính diện tích",
            explanation="Dùng công thức diện tích = ½|u⃗ × v⃗| cho mỗi tam giác. " + "; ".join(area_details),
            expression="S = Σ ½|→AB × →AC|",
            result=_fmt(total_area, 4),
            highlight=fp_names,
        ))

        return SolverResult(
            question=question,
            answer=f"Diện tích = {_fmt(total_area, 4)}",
            steps=steps,
            warnings=warnings,
        )

    # Fallback: triangle from first 3 points in question
    if len(point_names) >= 3:
        A_name, B_name, C_name = point_names[0], point_names[1], point_names[2]
        if all(n in pts for n in (A_name, B_name, C_name)):
            A, B, C = pts[A_name], pts[B_name], pts[C_name]
            AB = _sub(B, A)
            AC = _sub(C, A)
            cross = _cross(AB, AC)
            area = _norm(cross) / 2
            steps.append(SolverStep(
                index=1,
                title=f"Tính diện tích △{A_name}{B_name}{C_name}",
                explanation=f"S = ½|→{A_name}{B_name} × →{A_name}{C_name}| = {_fmt(area, 4)}",
                expression=f"S = ½|→{A_name}{B_name} × →{A_name}{C_name}|",
                result=_fmt(area, 4),
                highlight=[A_name, B_name, C_name],
            ))
            return SolverResult(question, f"Diện tích = {_fmt(area, 4)}", steps, warnings)

    warnings.append("Không đủ thông tin để tính diện tích. Hãy hỏi ví dụ: diện tích mặt ABCD.")
    return SolverResult(question, "Không xác định", steps, warnings)


# ---------------------------------------------------------------------------
# Volume solver
# ---------------------------------------------------------------------------

def _solve_volume(scene_dict: dict, pts: dict[str, Vec3], question: str, warnings: list[str]) -> SolverResult:
    steps: list[SolverStep] = []
    point_names = re.findall(r'\b([A-Z][0-9\']*)\b', question)
    known = [n for n in point_names if n in pts]

    if len(known) >= 4:
        # Tetrahedron from first 4 points
        A, B, C, D = [pts[n] for n in known[:4]]
        A_n, B_n, C_n, D_n = known[:4]
        AB = _sub(B, A)
        AC = _sub(C, A)
        AD = _sub(D, A)
        cross_bc = _cross(AB, AC)
        vol = abs(_dot(cross_bc, AD)) / 6

        steps.append(SolverStep(
            index=1,
            title=f"Xác định 4 đỉnh: {A_n}, {B_n}, {C_n}, {D_n}",
            explanation=f"Dùng công thức thể tích tứ diện: V = ⅙|({A_n}{B_n} × {A_n}{C_n}) · {A_n}{D_n}|",
            expression=None,
            result=None,
            highlight=known[:4],
        ))
        steps.append(SolverStep(
            index=2,
            title="Tính thể tích tứ diện",
            explanation=f"V = ⅙|det[{A_n}{B_n}, {A_n}{C_n}, {A_n}{D_n}]| = {_fmt(vol, 4)}",
            expression="V = ⅙|(→AB × →AC) · →AD|",
            result=_fmt(vol, 4),
            highlight=known[:4],
        ))
        return SolverResult(question, f"Thể tích = {_fmt(vol, 4)}", steps, warnings)

    warnings.append("Cần ít nhất 4 điểm để tính thể tích tứ diện. Hãy chỉ rõ các đỉnh.")
    return SolverResult(question, "Không xác định", steps, warnings)


# ---------------------------------------------------------------------------
# Parallel checker
# ---------------------------------------------------------------------------

def _solve_parallel(scene_dict: dict, pts: dict[str, Vec3], question: str, warnings: list[str]) -> SolverResult:
    steps: list[SolverStep] = []
    edges = re.findall(r'\b([A-Z]{2})\b', question)

    if len(edges) < 2:
        warnings.append("Cần hai đoạn/đường thẳng để kiểm tra song song (ví dụ: AB song song CD).")
        return SolverResult(question, "Không xác định", steps, warnings)

    e1, e2 = edges[0], edges[1]
    p1, p2 = e1[0], e1[1]
    p3, p4 = e2[0], e2[1]

    if not all(n in pts for n in (p1, p2, p3, p4)):
        missing = [n for n in (p1, p2, p3, p4) if n not in pts]
        warnings.append(f"Điểm {', '.join(missing)} không có trong scene.")
        return SolverResult(question, "Không xác định", steps, warnings)

    v1 = _sub(pts[p2], pts[p1])
    v2 = _sub(pts[p4], pts[p3])
    cross = _cross(v1, v2)
    is_parallel = _norm(cross) < 1e-8

    steps.append(SolverStep(
        index=1,
        title=f"Tính vector chỉ phương của {e1} và {e2}",
        explanation=f"→{e1} = ({_fmt(v1[0])}, {_fmt(v1[1])}, {_fmt(v1[2])})\n→{e2} = ({_fmt(v2[0])}, {_fmt(v2[1])}, {_fmt(v2[2])})",
        expression=None,
        result=None,
        highlight=list({p1, p2, p3, p4}),
    ))
    steps.append(SolverStep(
        index=2,
        title=f"Kiểm tra tích có hướng →{e1} × →{e2}",
        explanation=f"→{e1} × →{e2} = ({_fmt(cross[0])}, {_fmt(cross[1])}, {_fmt(cross[2])})\n"
                    + ("→ Tích có hướng = 0⃗, hai vector song song." if is_parallel else "→ Tích có hướng ≠ 0⃗, hai vector KHÔNG song song."),
        expression=f"→{e1} × →{e2} = ({_fmt(cross[0])}, {_fmt(cross[1])}, {_fmt(cross[2])})",
        result="Song song ✓" if is_parallel else "Không song song ✗",
        highlight=list({p1, p2, p3, p4}),
    ))

    answer = f"{e1} song song {e2}: {'ĐÚng' if is_parallel else 'SAI'}"
    return SolverResult(question, answer, steps, warnings)


# ---------------------------------------------------------------------------
# Perpendicular checker
# ---------------------------------------------------------------------------

def _solve_perpendicular(scene_dict: dict, pts: dict[str, Vec3], question: str, warnings: list[str]) -> SolverResult:
    steps: list[SolverStep] = []
    edges = re.findall(r'\b([A-Z]{2})\b', question)

    if len(edges) < 2:
        warnings.append("Cần hai đoạn để kiểm tra vuông góc (ví dụ: AB vuông góc CD).")
        return SolverResult(question, "Không xác định", steps, warnings)

    e1, e2 = edges[0], edges[1]
    p1, p2 = e1[0], e1[1]
    p3, p4 = e2[0], e2[1]

    if not all(n in pts for n in (p1, p2, p3, p4)):
        missing = [n for n in (p1, p2, p3, p4) if n not in pts]
        warnings.append(f"Điểm {', '.join(missing)} không có trong scene.")
        return SolverResult(question, "Không xác định", steps, warnings)

    v1 = _sub(pts[p2], pts[p1])
    v2 = _sub(pts[p4], pts[p3])
    dot = _dot(v1, v2)
    is_perp = abs(dot) < 1e-8

    steps.append(SolverStep(
        index=1,
        title=f"Tính vector chỉ phương",
        explanation=f"→{e1} = ({_fmt(v1[0])}, {_fmt(v1[1])}, {_fmt(v1[2])})\n→{e2} = ({_fmt(v2[0])}, {_fmt(v2[1])}, {_fmt(v2[2])})",
        expression=None,
        result=None,
        highlight=list({p1, p2, p3, p4}),
    ))
    steps.append(SolverStep(
        index=2,
        title=f"Kiểm tra tích vô hướng →{e1} · →{e2}",
        explanation=f"→{e1} · →{e2} = {_fmt(dot, 6)}\n"
                    + ("→ Tích vô hướng = 0, hai đường vuông góc." if is_perp else "→ Tích vô hướng ≠ 0, hai đường KHÔNG vuông góc."),
        expression=f"→{e1} · →{e2} = {_fmt(dot, 6)}",
        result="Vuông góc ✓" if is_perp else "Không vuông góc ✗",
        highlight=list({p1, p2, p3, p4}),
    ))

    answer = f"{e1} vuông góc {e2}: {'ĐÚNG' if is_perp else 'SAI'}"
    return SolverResult(question, answer, steps, warnings)
