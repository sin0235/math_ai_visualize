from app.schemas.scene import OcrProvider


ROUTER9_MODEL_PREFIXES = ("router9/", "gh/", "cc/", "github/", "codex-")
OPENROUTER_MODEL_PREFIXES = ("openrouter/", "openai/", "google/", "anthropic/", "meta-llama/", "mistralai/", "qwen/")


def infer_provider_from_model(model: str | None) -> str | None:
    if not model:
        return None
    if model.startswith(ROUTER9_MODEL_PREFIXES):
        return "router9"
    if model.startswith(OPENROUTER_MODEL_PREFIXES):
        return "openrouter"
    return None


def normalize_model_for_provider(provider: str, model: str | None) -> str | None:
    if provider == "router9" and model:
        return model.removeprefix("router9/")
    if provider == "openrouter" and model:
        return model.removeprefix("openrouter/")
    return model


def resolve_ocr_provider(provider: OcrProvider | None, model: str | None) -> OcrProvider:
    if provider is not None:
        return provider
    inferred = infer_provider_from_model(model)
    if inferred in {"router9", "openrouter"}:
        return inferred
    return "openrouter"
