"""Preset solid geometry scenes with proper Oxyz-aligned coordinates.

Convention: Place one vertex at the origin O, align base edges along Ox/Oz axes,
height along Oy.  This gives "nice" integer/simple coordinates.
"""

from app.schemas.scene import Annotation, MathScene, Relation, SceneView


def equilateral_triangle(problem_text: str, grade: int | None) -> MathScene:
    import math

    a = 3
    return MathScene(
        problem_text=problem_text,
        grade=grade,
        topic="solid_geometry",
        renderer="threejs_3d",
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": a, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": round(a / 2, 2), "y": 0, "z": round(a * math.sqrt(3) / 2, 2)},
            {"type": "face", "name": "ABC", "points": ["A", "B", "C"], "color": "#5da9ff", "opacity": 0.14},
        ],
        relations=[
            Relation(type="equal_length", object_1="AB", object_2="BC", metadata={"value": a}),
            Relation(type="equal_length", object_1="BC", object_2="CA", metadata={"value": a}),
        ],
        annotations=[
            Annotation(type="equal_marks", target="A-B", metadata={"group": 1}),
            Annotation(type="equal_marks", target="B-C", metadata={"group": 1}),
            Annotation(type="equal_marks", target="C-A", metadata={"group": 1}),
            Annotation(type="length", target="A-B", label=f"a = {a}"),
            Annotation(type="angle", target="A", label="60°", metadata={"arms": ["B", "C"]}),
            Annotation(type="angle", target="B", label="60°", metadata={"arms": ["A", "C"]}),
            Annotation(type="angle", target="C", label="60°", metadata={"arms": ["A", "B"]}),
        ],
        view=SceneView(dimension="3d", show_axes=True, show_grid=True, show_coordinates=True),
    )


def square_pyramid(problem_text: str, grade: int | None) -> MathScene:
    """S.ABCD — square base ABCD, SA ⊥ (ABCD).

    A at origin, AB along +x, AD along +z, SA along +y.
    Default side = 3, height SA = 3.
    """
    a = 3  # base side
    h = 3  # height

    return MathScene(
        problem_text=problem_text,
        grade=grade,
        topic="solid_geometry",
        renderer="threejs_3d",
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": a, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": a, "y": 0, "z": a},
            {"type": "point_3d", "name": "D", "x": 0, "y": 0, "z": a},
            {"type": "point_3d", "name": "S", "x": 0, "y": h, "z": 0},
            # faces
            {"type": "face", "name": "ABCD", "points": ["A", "B", "C", "D"], "color": "#5da9ff", "opacity": 0.15},
            {"type": "face", "name": "SAB", "points": ["S", "A", "B"], "color": "#ffb86b", "opacity": 0.18},
            {"type": "face", "name": "SBC", "points": ["S", "B", "C"], "color": "#ffd166", "opacity": 0.14},
            {"type": "face", "name": "SCD", "points": ["S", "C", "D"], "color": "#c9a0dc", "opacity": 0.14},
            {"type": "face", "name": "SDA", "points": ["S", "D", "A"], "color": "#7fcdbb", "opacity": 0.14},
        ],
        relations=[
            Relation(type="perpendicular", object_1="SA", object_2="plane(ABCD)"),
            Relation(type="equal_length", object_1="AB", object_2="BC", metadata={"value": a}),
            Relation(type="equal_length", object_1="BC", object_2="CD", metadata={"value": a}),
            Relation(type="equal_length", object_1="CD", object_2="DA", metadata={"value": a}),
        ],
        annotations=[
            Annotation(type="right_angle", target="A", metadata={"arms": ["S", "B"]}),
            Annotation(type="right_angle", target="A", metadata={"arms": ["S", "D"]}),
            Annotation(type="equal_marks", target="A-B", metadata={"group": 1}),
            Annotation(type="equal_marks", target="B-C", metadata={"group": 1}),
            Annotation(type="equal_marks", target="C-D", metadata={"group": 1}),
            Annotation(type="equal_marks", target="D-A", metadata={"group": 1}),
            Annotation(type="length", target="A-B", label=f"a = {a}"),
            Annotation(type="length", target="S-A", label=f"h = {h}"),
        ],
        view=SceneView(dimension="3d", show_axes=True, show_grid=True, show_coordinates=True),
    )


def triangular_pyramid(problem_text: str, grade: int | None) -> MathScene:
    """S.ABC — tetrahedron.

    A at origin, B along +x, C in xz-plane, S above.
    Default: equilateral base side = 3, SA ⊥ (ABC), SA = 3.
    """
    import math
    a = 3
    h = 3

    cx = a / 2
    cz = a * math.sqrt(3) / 2

    return MathScene(
        problem_text=problem_text,
        grade=grade,
        topic="solid_geometry",
        renderer="threejs_3d",
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": a, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": round(cx, 2), "y": 0, "z": round(cz, 2)},
            {"type": "point_3d", "name": "S", "x": 0, "y": h, "z": 0},
            # faces
            {"type": "face", "name": "ABC", "points": ["A", "B", "C"], "color": "#5da9ff", "opacity": 0.15},
            {"type": "face", "name": "SAB", "points": ["S", "A", "B"], "color": "#ffb86b", "opacity": 0.18},
            {"type": "face", "name": "SBC", "points": ["S", "B", "C"], "color": "#ffd166", "opacity": 0.14},
            {"type": "face", "name": "SCA", "points": ["S", "C", "A"], "color": "#c9a0dc", "opacity": 0.14},
        ],
        relations=[
            Relation(type="perpendicular", object_1="SA", object_2="plane(ABC)"),
        ],
        annotations=[
            Annotation(type="right_angle", target="A", metadata={"arms": ["S", "B"]}),
            Annotation(type="right_angle", target="A", metadata={"arms": ["S", "C"]}),
            Annotation(type="length", target="S-A", label=f"h = {h}"),
            Annotation(type="equal_marks", target="A-B", metadata={"group": 1}),
            Annotation(type="equal_marks", target="B-C", metadata={"group": 1}),
            Annotation(type="equal_marks", target="C-A", metadata={"group": 1}),
        ],
        view=SceneView(dimension="3d", show_axes=True, show_grid=True, show_coordinates=True),
    )


def triangular_prism(problem_text: str, grade: int | None) -> MathScene:
    """ABC.A'B'C' — triangular prism.

    A at origin, AB along +x, AC in xz-plane, height along +y.
    """
    import math
    a = 3
    h = 3

    cx = a / 2
    cz = a * math.sqrt(3) / 2

    return MathScene(
        problem_text=problem_text,
        grade=grade,
        topic="solid_geometry",
        renderer="threejs_3d",
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": a, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": round(cx, 2), "y": 0, "z": round(cz, 2)},
            {"type": "point_3d", "name": "A'", "x": 0, "y": h, "z": 0},
            {"type": "point_3d", "name": "B'", "x": a, "y": h, "z": 0},
            {"type": "point_3d", "name": "C'", "x": round(cx, 2), "y": h, "z": round(cz, 2)},
            # faces
            {"type": "face", "name": "ABC", "points": ["A", "B", "C"], "color": "#5da9ff", "opacity": 0.12},
            {"type": "face", "name": "A'B'C'", "points": ["A'", "B'", "C'"], "color": "#5da9ff", "opacity": 0.12},
            {"type": "face", "name": "ABB'A'", "points": ["A", "B", "B'", "A'"], "color": "#ffd166", "opacity": 0.12},
            {"type": "face", "name": "BCC'B'", "points": ["B", "C", "C'", "B'"], "color": "#c9a0dc", "opacity": 0.12},
            {"type": "face", "name": "CAA'C'", "points": ["C", "A", "A'", "C'"], "color": "#7fcdbb", "opacity": 0.12},
        ],
        relations=[
            Relation(type="equal_length", object_1="AB", object_2="BC", metadata={"value": a}),
            Relation(type="equal_length", object_1="AA'", object_2="BB'", metadata={"value": h}),
        ],
        annotations=[
            Annotation(type="equal_marks", target="A-B", metadata={"group": 1}),
            Annotation(type="equal_marks", target="B-C", metadata={"group": 1}),
            Annotation(type="equal_marks", target="C-A", metadata={"group": 1}),
            Annotation(type="equal_marks", target="A-A'", metadata={"group": 2}),
            Annotation(type="equal_marks", target="B-B'", metadata={"group": 2}),
            Annotation(type="equal_marks", target="C-C'", metadata={"group": 2}),
            Annotation(type="right_angle", target="A", metadata={"arms": ["B", "A'"]}),
            Annotation(type="length", target="A-B", label=f"a = {a}"),
        ],
        view=SceneView(dimension="3d", show_axes=True, show_grid=True, show_coordinates=True),
    )


def rectangular_box(problem_text: str, grade: int | None) -> MathScene:
    """ABCD.A'B'C'D' — rectangular box.

    A at origin, AB along +x (length), AD along +z (width), AA' along +y (height).
    """
    length = 4
    width = 3
    height = 3

    return MathScene(
        problem_text=problem_text,
        grade=grade,
        topic="solid_geometry",
        renderer="threejs_3d",
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": length, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": length, "y": 0, "z": width},
            {"type": "point_3d", "name": "D", "x": 0, "y": 0, "z": width},
            {"type": "point_3d", "name": "A'", "x": 0, "y": height, "z": 0},
            {"type": "point_3d", "name": "B'", "x": length, "y": height, "z": 0},
            {"type": "point_3d", "name": "C'", "x": length, "y": height, "z": width},
            {"type": "point_3d", "name": "D'", "x": 0, "y": height, "z": width},
            # faces
            {"type": "face", "name": "ABCD", "points": ["A", "B", "C", "D"], "color": "#5da9ff", "opacity": 0.10},
            {"type": "face", "name": "A'B'C'D'", "points": ["A'", "B'", "C'", "D'"], "color": "#ffb86b", "opacity": 0.12},
            {"type": "face", "name": "ABB'A'", "points": ["A", "B", "B'", "A'"], "color": "#ffd166", "opacity": 0.12},
            {"type": "face", "name": "BCC'B'", "points": ["B", "C", "C'", "B'"], "color": "#c9a0dc", "opacity": 0.10},
            {"type": "face", "name": "CDD'C'", "points": ["C", "D", "D'", "C'"], "color": "#7fcdbb", "opacity": 0.10},
            {"type": "face", "name": "DAA'D'", "points": ["D", "A", "A'", "D'"], "color": "#f0b8b8", "opacity": 0.10},
        ],
        relations=[
            Relation(type="equal_length", object_1="AB", object_2="CD", metadata={"value": length}),
            Relation(type="equal_length", object_1="AD", object_2="BC", metadata={"value": width}),
            Relation(type="equal_length", object_1="AA'", object_2="BB'", metadata={"value": height}),
            Relation(type="perpendicular", object_1="AB", object_2="AD"),
            Relation(type="perpendicular", object_1="AB", object_2="AA'"),
            Relation(type="perpendicular", object_1="AD", object_2="AA'"),
        ],
        annotations=[
            Annotation(type="right_angle", target="A", metadata={"arms": ["B", "D"]}),
            Annotation(type="right_angle", target="A", metadata={"arms": ["B", "A'"]}),
            Annotation(type="right_angle", target="A", metadata={"arms": ["D", "A'"]}),
            Annotation(type="equal_marks", target="A-B", metadata={"group": 1}),
            Annotation(type="equal_marks", target="C-D", metadata={"group": 1}),
            Annotation(type="equal_marks", target="A'-B'", metadata={"group": 1}),
            Annotation(type="equal_marks", target="C'-D'", metadata={"group": 1}),
            Annotation(type="equal_marks", target="A-D", metadata={"group": 2}),
            Annotation(type="equal_marks", target="B-C", metadata={"group": 2}),
            Annotation(type="equal_marks", target="A'-D'", metadata={"group": 2}),
            Annotation(type="equal_marks", target="B'-C'", metadata={"group": 2}),
            Annotation(type="equal_marks", target="A-A'", metadata={"group": 3}),
            Annotation(type="equal_marks", target="B-B'", metadata={"group": 3}),
            Annotation(type="equal_marks", target="C-C'", metadata={"group": 3}),
            Annotation(type="equal_marks", target="D-D'", metadata={"group": 3}),
            Annotation(type="length", target="A-B", label=f"{length}"),
            Annotation(type="length", target="A-D", label=f"{width}"),
            Annotation(type="length", target="A-A'", label=f"{height}"),
        ],
        view=SceneView(dimension="3d", show_axes=True, show_grid=True, show_coordinates=True),
    )
