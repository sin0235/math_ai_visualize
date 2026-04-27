import re
from typing import Any

from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.schemas.scene import MathScene, SceneView
from app.services.nvidia_client import NvidiaClient
from app.services.openrouter_client import OpenRouterClient
from app.services.solid_presets import equilateral_triangle, rectangular_box, square_pyramid, triangular_prism, triangular_pyramid

_POINT_2D_RE = re.compile(r"([A-Z])\s*\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)")
_POINT_3D_RE = re.compile(r"([A-Z])\s*\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)")
_FUNCTION_RE = re.compile(r"y\s*=\s*([^.,;\n]+)", re.IGNORECASE)
_CIRCLE_RADIUS_RE = re.compile(r"(?:tâm|tam)\s+([A-Z]).*?(?:bán kính|ban kinh|r)\s*[=:]?\s*(\d+(?:\.\d+)?)", re.IGNORECASE)


async def extract_scene(
    problem_text: str,
    grade: int | None = None,
    preferred_ai_provider: str | None = None,
) -> tuple[MathScene, list[str]]:
    settings = get_settings()
    warnings: list[str] = []

    for provider in _provider_order(settings, preferred_ai_provider):
        try:
            scene_json = await _extract_with_provider(provider, settings, problem_text, grade)
            return MathScene.model_validate(scene_json), warnings
        except (RuntimeError, ValidationError, ValueError, KeyError) as error:
            warnings.append(f"AI provider {provider} không dùng được: {error}")
        except Exception as error:
            warnings.append(f"AI provider {provider} lỗi: {error}")

    warnings.append("Đang dùng mock extractor vì AI provider chưa sẵn sàng.")
    return extract_scene_mock(problem_text, grade), warnings


def extract_scene_mock(problem_text: str, grade: int | None = None) -> MathScene:
    text = problem_text.strip()
    lowered = text.lower()

    if "tam giác đều" in lowered or "tam giac deu" in lowered:
        return equilateral_triangle(text, grade)
    if "lăng trụ" in lowered or "lang tru" in lowered:
        return triangular_prism(text, grade)
    if "hình hộp" in lowered or "hinh hop" in lowered or "hộp chữ nhật" in lowered:
        return rectangular_box(text, grade)
    if "tứ diện" in lowered or "tu dien" in lowered or "s.abc" in lowered:
        return triangular_pyramid(text, grade)
    if "hình chóp" in lowered or "s.abcd" in lowered:
        return square_pyramid(text, grade)

    points_3d = _extract_points_3d(text)
    if points_3d:
        return _coordinate_3d_scene(text, grade, points_3d)

    function_match = _FUNCTION_RE.search(text)
    if "đồ thị" in lowered or "do thi" in lowered or function_match:
        expression = function_match.group(1).strip() if function_match else "x^2"
        return MathScene(
            problem_text=text,
            grade=grade,
            topic="function_graph",
            renderer="geogebra_2d",
            objects=[{"type": "function_graph", "name": "f", "expression": expression}],
            view=SceneView(dimension="2d"),
        )

    points = _extract_points_2d(text)
    if "đường tròn" in lowered or "duong tron" in lowered:
        return _circle_scene(text, grade, points)
    if "vector" in lowered or "vectơ" in lowered or "vec" in lowered:
        return _vector_scene(text, grade, points)
    if points:
        return _coordinate_2d_scene(text, grade, points)

    return MathScene(
        problem_text=text,
        grade=grade,
        topic="unknown",
        renderer="geogebra_2d",
        objects=[],
        view=SceneView(dimension="2d"),
    )


def _extract_points_2d(text: str) -> list[dict[str, Any]]:
    return [
        {"type": "point_2d", "name": name, "x": float(x), "y": float(y)}
        for name, x, y in _POINT_2D_RE.findall(text)
    ]


def _extract_points_3d(text: str) -> list[dict[str, Any]]:
    return [
        {"type": "point_3d", "name": name, "x": float(x), "y": float(y), "z": float(z)}
        for name, x, y, z in _POINT_3D_RE.findall(text)
    ]


def _coordinate_2d_scene(text: str, grade: int | None, points: list[dict[str, Any]]) -> MathScene:
    objects: list[dict[str, Any]] = [*points]
    names = [point["name"] for point in points]
    if len(names) >= 2:
        objects.append({"type": "line_2d", "name": f"{names[0]}{names[1]}", "through": names[:2]})
    return MathScene(
        problem_text=text,
        grade=grade,
        topic="coordinate_2d",
        renderer="geogebra_2d",
        objects=objects,
        view=SceneView(dimension="2d"),
    )


def _coordinate_3d_scene(text: str, grade: int | None, points: list[dict[str, Any]]) -> MathScene:
    objects: list[dict[str, Any]] = [*points]
    names = [point["name"] for point in points]
    for start, end in zip(names, names[1:]):
        objects.append({"type": "segment", "points": [start, end]})
    return MathScene(
        problem_text=text,
        grade=grade,
        topic="coordinate_3d",
        renderer="threejs_3d",
        objects=objects,
        view=SceneView(dimension="3d", show_axes=True, show_grid=True),
    )


def _vector_scene(text: str, grade: int | None, points: list[dict[str, Any]]) -> MathScene:
    if len(points) < 2:
        points = [
            {"type": "point_2d", "name": "A", "x": 0, "y": 0},
            {"type": "point_2d", "name": "B", "x": 3, "y": 2},
        ]
    names = [point["name"] for point in points]
    return MathScene(
        problem_text=text,
        grade=grade,
        topic="vector_2d",
        renderer="geogebra_2d",
        objects=[*points, {"type": "vector_2d", "name": f"u", "from_point": names[0], "to_point": names[1]}],
        view=SceneView(dimension="2d"),
    )


def _circle_scene(text: str, grade: int | None, points: list[dict[str, Any]]) -> MathScene:
    objects: list[dict[str, Any]] = [*points]
    radius_match = _CIRCLE_RADIUS_RE.search(text)
    if radius_match:
        center, radius = radius_match.groups()
        if not any(point["name"] == center for point in points):
            objects.append({"type": "point_2d", "name": center, "x": 0, "y": 0})
        objects.append({"type": "circle_2d", "name": "c", "center": center, "radius": float(radius)})
    elif len(points) >= 2:
        objects.append({"type": "circle_2d", "name": "c", "center": points[0]["name"], "through": points[1]["name"]})
    else:
        objects.extend([
            {"type": "point_2d", "name": "O", "x": 0, "y": 0},
            {"type": "point_2d", "name": "A", "x": 2, "y": 0},
            {"type": "circle_2d", "name": "c", "center": "O", "through": "A"},
        ])
    return MathScene(
        problem_text=text,
        grade=grade,
        topic="coordinate_2d",
        renderer="geogebra_2d",
        objects=objects,
        view=SceneView(dimension="2d"),
    )


def _provider_order(settings: Settings, preferred_ai_provider: str | None = None) -> list[str]:
    provider = preferred_ai_provider or settings.ai_provider
    if provider == "mock":
        return []
    if provider in {"nvidia", "nvidia_v4_flash", "nvidia_kimi_k2"}:
        return _dedupe([provider, "openrouter", "openrouter_gpt_oss"])
    if provider in {"openrouter", "openrouter_gpt_oss"}:
        return _dedupe([provider, "nvidia", "nvidia_v4_flash", "nvidia_kimi_k2"])
    return _dedupe(["nvidia", "nvidia_v4_flash", "nvidia_kimi_k2", "openrouter", "openrouter_gpt_oss"])


def _dedupe(providers: list[str]) -> list[str]:
    seen = set()
    ordered = []
    for provider in providers:
        if provider in seen:
            continue
        seen.add(provider)
        ordered.append(provider)
    return ordered


async def _extract_with_provider(provider: str, settings: Settings, problem_text: str, grade: int | None) -> dict:
    if provider == "nvidia":
        return await NvidiaClient(settings).extract_scene_json(problem_text, grade)
    if provider == "nvidia_v4_flash":
        return await NvidiaClient(settings, model="deepseek-ai/deepseek-v4-flash", reasoning_effort="high").extract_scene_json(problem_text, grade)
    if provider == "nvidia_kimi_k2":
        return await NvidiaClient(settings, model="moonshotai/kimi-k2-thinking", thinking=False).extract_scene_json(problem_text, grade)
    if provider == "openrouter":
        return await OpenRouterClient(settings).extract_scene_json(problem_text, grade)
    if provider == "openrouter_gpt_oss":
        return await OpenRouterClient(settings, model="openai/gpt-oss-120b:free", reasoning_enabled=True).extract_scene_json(problem_text, grade)
    raise RuntimeError(f"Provider không hỗ trợ: {provider}")
