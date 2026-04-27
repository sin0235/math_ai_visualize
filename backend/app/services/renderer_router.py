from app.renderers.geogebra_commands import build_geogebra_commands
from app.renderers.three_scene import build_three_scene
from app.schemas.scene import MathScene, RenderPayload


def build_render_payload(scene: MathScene) -> RenderPayload:
    if scene.renderer.startswith("geogebra"):
        return RenderPayload(renderer=scene.renderer, geogebra_commands=build_geogebra_commands(scene))

    return RenderPayload(renderer=scene.renderer, three_scene=build_three_scene(scene))
