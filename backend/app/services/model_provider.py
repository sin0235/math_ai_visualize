from app.schemas.scene import OcrProvider


ROUTER9_MODEL_PREFIXES = (
    "router9/",
    "gh/",
    "cc/",
    "cx/",
    "oc/",
    "kr/",
    "cf/",
    "claude-ds/",
    "openAI-ds/",
    "kc/",
    "github/",
    "codex-",
)
OPENROUTER_MODEL_PREFIXES = ("openrouter/", "openai/", "google/", "anthropic/", "meta-llama/", "mistralai/", "qwen/")
NVIDIA_MODEL_PREFIXES = ("nvidia/",)
OLLAMA_MODEL_PREFIXES = ("ollama/",)
OPENAI_COMPAT_MODEL_PREFIXES = ("openai_compat/", "openai-compat/")


def infer_provider_from_model(model: str | None) -> str | None:
    if not model:
        return None
    if model.startswith(ROUTER9_MODEL_PREFIXES):
        return "router9"
    if model.startswith(NVIDIA_MODEL_PREFIXES):
        return "nvidia"
    if model.startswith(OLLAMA_MODEL_PREFIXES):
        return "ollama"
    if model.startswith(OPENAI_COMPAT_MODEL_PREFIXES):
        return "openai_compat"
    if model.startswith(OPENROUTER_MODEL_PREFIXES):
        return "openrouter"
    return None


def normalize_model_for_provider(provider: str, model: str | None) -> str | None:
    if provider == "router9" and model:
        return model.removeprefix("router9/")
    if provider == "openrouter" and model:
        return model.removeprefix("openrouter/")
    if provider == "nvidia" and model:
        return model.removeprefix("nvidia/")
    if provider == "ollama" and model:
        return model.removeprefix("ollama/")
    if provider == "openai_compat" and model:
        return model.removeprefix("openai_compat/").removeprefix("openai-compat/")
    return model


def resolve_ocr_provider(provider: OcrProvider | None, model: str | None) -> OcrProvider:
    if provider is not None:
        return provider
    inferred = infer_provider_from_model(model)
    if inferred in {"router9", "openrouter", "nvidia", "ollama", "openai_compat"}:
        return inferred
    return "openrouter"
