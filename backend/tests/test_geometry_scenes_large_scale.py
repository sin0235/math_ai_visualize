import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.schemas.scene import MathScene, AdvancedRenderSettings
from app.services.geometry_engine import normalize_scene
from app.services.renderer_router import build_render_payload
from app.api.deps import require_active_user

# Setup 100 test cases programmatically
def make_geometry_scene(objects, relations=None, annotations=None, renderer="threejs_3d", dimension="3d"):
    return {
        "problem_text": "Geometry Benchmark Scene",
        "renderer": renderer,
        "view": {"dimension": dimension, "show_axes": True, "show_grid": True, "show_coordinates": False},
        "objects": objects,
        "relations": relations or [],
        "annotations": annotations or []
    }

test_cases = []

# 1-10: 2D Points
for i in range(10):
    test_cases.append((
        f"2d_points_{i}",
        make_geometry_scene(
            objects=[
                {"type": "point_2d", "name": "A", "x": float(i), "y": 2.0},
                {"type": "point_2d", "name": "B", "x": 3.0, "y": float(i * 1.5)},
            ],
            dimension="2d",
            renderer="geogebra_2d"
        )
    ))

# 11-20: 3D Points
for i in range(10):
    test_cases.append((
        f"3d_points_{i}",
        make_geometry_scene(
            objects=[
                {"type": "point_3d", "name": "A", "x": float(i), "y": 2.0, "z": -1.0},
                {"type": "point_3d", "name": "B", "x": 3.0, "y": float(i * 1.5), "z": 4.0},
            ],
            dimension="3d",
            renderer="threejs_3d"
        )
    ))

# 21-30: Segments
for i in range(10):
    style = ["solid", "dashed", "dotted"][i % 3]
    color = ["#ff0000", "#00ff00", "#0000ff"][i % 3]
    test_cases.append((
        f"segments_{i}",
        make_geometry_scene(
            objects=[
                {"type": "point_3d", "name": "A", "x": 0.0, "y": 0.0, "z": 0.0},
                {"type": "point_3d", "name": "B", "x": float(i + 1), "y": 2.0, "z": 1.0},
                {"type": "segment", "name": "AB", "points": ["A", "B"], "hidden": i % 2 == 0, "style": style, "color": color, "line_width": float(i + 1)}
            ]
        )
    ))

# 31-40: Lines
for i in range(10):
    test_cases.append((
        f"lines_{i}",
        make_geometry_scene(
            objects=[
                {"type": "point_3d", "name": "A", "x": 0.0, "y": 0.0, "z": 0.0},
                {"type": "point_3d", "name": "B", "x": float(i + 1), "y": 1.0, "z": 0.0},
                {"type": "line_3d", "name": f"line_{i}", "through": ["A", "B"], "color": "#123456"}
            ]
        )
    ))

# 41-50: Circles
for i in range(10):
    test_cases.append((
        f"circles_{i}",
        make_geometry_scene(
            objects=[
                {"type": "point_2d", "name": "O", "x": float(i), "y": 0.0},
                {"type": "circle_2d", "name": f"C_{i}", "center": "O", "radius": float(i + 1.5)}
            ],
            dimension="2d",
            renderer="geogebra_2d"
        )
    ))

# 51-60: Spheres
for i in range(10):
    test_cases.append((
        f"spheres_{i}",
        make_geometry_scene(
            objects=[
                {"type": "point_3d", "name": "O", "x": 0.0, "y": float(i), "z": 0.0},
                {"type": "sphere", "name": f"S_{i}", "center": "O", "radius": float(i * 0.5 + 1.0)}
            ]
        )
    ))

# 61-68: Faces
for i in range(8):
    test_cases.append((
        f"faces_{i}",
        make_geometry_scene(
            objects=[
                {"type": "point_3d", "name": "A", "x": 0.0, "y": 0.0, "z": 0.0},
                {"type": "point_3d", "name": "B", "x": float(i + 1), "y": 0.0, "z": 0.0},
                {"type": "point_3d", "name": "C", "x": 0.0, "y": float(i + 1), "z": 0.0},
                {"type": "face", "name": f"F_{i}", "points": ["A", "B", "C"], "color": "#aabbcc", "opacity": 0.5}
            ]
        )
    ))

# 69-75: Planes
for i in range(7):
    test_cases.append((
        f"planes_{i}",
        make_geometry_scene(
            objects=[
                {"type": "point_3d", "name": "A", "x": 0.0, "y": 0.0, "z": 0.0},
                {"type": "point_3d", "name": "B", "x": float(i + 2), "y": 0.0, "z": 0.0},
                {"type": "point_3d", "name": "C", "x": 0.0, "y": float(i + 2), "z": 0.0},
                {"type": "plane", "name": f"P_{i}", "points": ["A", "B", "C"], "color": "#112233", "opacity": 0.3}
            ]
        )
    ))

# 76-80: Midpoint Relations
for i in range(5):
    mx = 1.0 if i == 0 else 1.0 + float(i) * 0.1
    test_cases.append((
        f"relations_midpoint_{i}",
        make_geometry_scene(
            objects=[
                {"type": "point_3d", "name": "A", "x": 0.0, "y": 0.0, "z": 0.0},
                {"type": "point_3d", "name": "B", "x": 2.0, "y": 0.0, "z": 0.0},
                {"type": "point_3d", "name": "M", "x": mx, "y": 0.0, "z": 0.0},
            ],
            relations=[
                {"type": "midpoint", "object_1": "M", "object_2": "A-B"}
            ]
        )
    ))

# 81-85: Perpendicular Relations
for i in range(5):
    bx = 0.0 if i == 0 else float(i) * 0.05
    test_cases.append((
        f"relations_perpendicular_{i}",
        make_geometry_scene(
            objects=[
                {"type": "point_3d", "name": "O", "x": 0.0, "y": 0.0, "z": 0.0},
                {"type": "point_3d", "name": "A", "x": 1.0, "y": 0.0, "z": 0.0},
                {"type": "point_3d", "name": "B", "x": bx, "y": 1.0, "z": 0.0},
            ],
            relations=[
                {"type": "perpendicular", "object_1": "O-A", "object_2": "O-B"}
            ]
        )
    ))

# 86-90: Parallel Relations
for i in range(5):
    dy = 1.0 if i == 0 else 1.0 + float(i) * 0.1
    test_cases.append((
        f"relations_parallel_{i}",
        make_geometry_scene(
            objects=[
                {"type": "point_3d", "name": "A", "x": 0.0, "y": 0.0, "z": 0.0},
                {"type": "point_3d", "name": "B", "x": 2.0, "y": 0.0, "z": 0.0},
                {"type": "point_3d", "name": "C", "x": 0.0, "y": dy, "z": 0.0},
                {"type": "point_3d", "name": "D", "x": 2.0, "y": dy, "z": 0.0},
            ],
            relations=[
                {"type": "parallel", "object_1": "A-B", "object_2": "C-D"}
            ]
        )
    ))

# 91-95: Ratio Relations
for i in range(5):
    mx = 1.0 if i == 0 else 1.0 + float(i) * 0.1
    test_cases.append((
        f"relations_ratio_{i}",
        make_geometry_scene(
            objects=[
                {"type": "point_3d", "name": "A", "x": 0.0, "y": 0.0, "z": 0.0},
                {"type": "point_3d", "name": "B", "x": 4.0, "y": 0.0, "z": 0.0},
                {"type": "point_3d", "name": "M", "x": mx, "y": 0.0, "z": 0.0},
            ],
            relations=[
                {"type": "ratio", "object_1": "M", "object_2": "A-B", "metadata": {"value": 0.25}}
            ]
        )
    ))

# 96-100: Complex Relations
for i in range(5):
    px = 5.0 if i == 0 else 5.0 + float(i) * 0.1
    test_cases.append((
        f"relations_complex_{i}",
        make_geometry_scene(
            objects=[
                {"type": "point_3d", "name": "O", "x": 0.0, "y": 0.0, "z": 0.0},
                {"type": "point_3d", "name": "P", "x": px, "y": 0.0, "z": 0.0},
                {"type": "sphere", "name": "S", "center": "O", "radius": 5.0}
            ],
            relations=[
                {"type": "on_sphere", "object_1": "P", "object_2": "S"}
            ]
        )
    ))

@pytest.mark.parametrize("name,scene_dict", test_cases)
def test_geometry_scenes_large_scale(name, scene_dict):
    # 1. Pydantic validate
    scene = MathScene.model_validate(scene_dict)
    assert scene.renderer in ("threejs_3d", "geogebra_2d", "geogebra_3d")

    # 2. Engine normalization & payload build
    settings = AdvancedRenderSettings()
    normalized = normalize_scene(scene, settings)
    payload = build_render_payload(normalized, settings)

    assert payload.renderer == scene.renderer
    if scene.renderer == "threejs_3d":
        assert payload.three_scene is not None
    else:
        assert payload.geogebra_commands is not None

def test_api_render_scene_with_all_cases(monkeypatch):
    async def mock_active_user():
        return None

    async def mock_noop(*args, **kwargs):
        return None

    app.dependency_overrides[require_active_user] = mock_active_user
    monkeypatch.setattr("app.api.routes_render.enforce_rate_limit", mock_noop)
    monkeypatch.setattr("app.api.routes_render.enforce_render_access", mock_noop)

    try:
        client = TestClient(app)
        # We test a sample of the generated scenarios through the real HTTP API router
        for name, scene_dict in test_cases[::10]:  # Test 10 representative samples from the 100 cases
            response = client.post("/api/render/scene", json={
                "scene": scene_dict,
                "advanced_settings": {}
            })
            assert response.status_code == 200
            payload = response.json()
            assert "scene" in payload
            assert "payload" in payload
            assert "cas_issues" in payload
    finally:
        app.dependency_overrides.clear()
