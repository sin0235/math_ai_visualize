from app.renderers.geogebra_commands import build_geogebra_commands
from app.renderers.three_scene import build_three_scene
from app.schemas.scene import (
    AdvancedRenderSettings,
    Face,
    FunctionGraph,
    MathScene,
    Plane,
    Point2D,
    Point3D,
    RenderPayload,
    Renderer,
    RendererCompatibilityReport,
    Sphere,
)


def validate_renderer_compatibility(scene: MathScene, requested_renderer: Renderer | None = None) -> RendererCompatibilityReport:
    renderer = requested_renderer or scene.renderer
    point_3d_count = sum(1 for obj in scene.objects if isinstance(obj, Point3D))
    point_2d_count = sum(1 for obj in scene.objects if isinstance(obj, Point2D))
    has_3d_objects = any(isinstance(obj, (Point3D, Face, Plane, Sphere)) for obj in scene.objects)
    has_function_graph = any(isinstance(obj, FunctionGraph) for obj in scene.objects)
    messages: list[str] = []
    unsupported_objects: list[str] = []

    if renderer == "geogebra_2d" and has_3d_objects:
        messages.append("GeoGebra 2D không tương thích với scene có đối tượng 3D.")
        unsupported_objects.extend(
            getattr(obj, "name", None) or obj.type
            for obj in scene.objects
            if isinstance(obj, (Point3D, Face, Plane, Sphere))
        )
    if renderer == "threejs_3d" and (point_2d_count > 0 or has_function_graph) and point_3d_count == 0:
        messages.append("Three.js 3D cần scene 3D hoặc bước chuyển đổi 2D sang 3D rõ ràng.")
        unsupported_objects.extend(
            getattr(obj, "name", None) or obj.type
            for obj in scene.objects
            if isinstance(obj, (Point2D, FunctionGraph))
        )
    if renderer == "geogebra_2d" and scene.view.dimension != "2d":
        messages.append("Renderer GeoGebra 2D yêu cầu view.dimension='2d'.")
    if renderer in {"geogebra_3d", "threejs_3d"} and scene.view.dimension != "3d" and has_3d_objects:
        messages.append("Renderer 3D yêu cầu view.dimension='3d' khi scene có đối tượng 3D.")

    return RendererCompatibilityReport(
        status="incompatible" if messages else "compatible",
        renderer=renderer,
        dimension=scene.view.dimension,
        messages=messages,
        unsupported_objects=unsupported_objects,
    )


def build_render_payload(scene: MathScene, settings: AdvancedRenderSettings | None = None) -> RenderPayload:
    compatibility = validate_renderer_compatibility(scene)
    if compatibility.status == "incompatible":
        raise ValueError("; ".join(compatibility.messages) or "Renderer không tương thích với scene.")
    if scene.renderer.startswith("geogebra"):
        return RenderPayload(renderer=scene.renderer, geogebra_commands=build_geogebra_commands(scene, settings))

    return RenderPayload(renderer=scene.renderer, three_scene=build_three_scene(scene))
