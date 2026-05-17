from dataclasses import dataclass

from app.schemas.scene import OcrProvider


CANONICAL_PROVIDERS = {"openrouter", "nvidia", "ollama", "openai_compat", "router9"}
REGISTRY_PROVIDERS = ("openrouter", "nvidia", "ollama", "openai_compat", "router9")
PROVIDER_ALIASES = {
    "ollama_gpt_oss": "ollama",
    "openrouter_gpt_oss": "openrouter",
    "opencode_nemotron": "openrouter",
    "openai-compat": "openai_compat",
}


@dataclass(frozen=True)
class CanonicalModelRef:
    provider_id: str
    model_id: str
    changed: bool = False
    warning: str | None = None


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
EXPLICIT_PROVIDER_PREFIXES = {
    "router9": ("router9/",),
    "openrouter": ("openrouter/",),
    "nvidia": ("nvidia/",),
    "ollama": ("ollama/",),
    "openai_compat": ("openai_compat/", "openai-compat/"),
}


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


def canonical_provider_id(provider: str | None) -> str | None:
    if provider is None:
        return None
    provider = provider.strip()
    return PROVIDER_ALIASES.get(provider, provider)


def normalize_provider_defaults(value: dict | None) -> dict | None:
    if value is None:
        return None
    normalized = dict(value)
    for provider_id in REGISTRY_PROVIDERS:
        provider = normalized.get(provider_id)
        if not isinstance(provider, dict):
            continue
        provider_normalized = dict(provider)
        if provider_id != "router9":
            provider_normalized.pop("only_mode", None)
        allowed = provider_normalized.get("allowed_model_ids")
        model = provider_normalized.get("model")
        if isinstance(allowed, list) and allowed and isinstance(model, str) and model and model not in allowed:
            provider_normalized["model"] = str(allowed[0])
        normalized[provider_id] = provider_normalized
    return normalized


def normalize_model_for_provider(provider: str, model: str | None) -> str | None:
    provider = canonical_provider_id(provider) or provider
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


def explicit_provider_from_model(model: str | None) -> str | None:
    if not model:
        return None
    for provider_id, prefixes in EXPLICIT_PROVIDER_PREFIXES.items():
        if model.startswith(prefixes):
            return provider_id
    return None


def canonicalize_model_ref(provider: str | None, model: str | None, *, strict: bool = True, allow_auto: bool = True) -> CanonicalModelRef:
    raw_provider = (canonical_provider_id(provider) or "auto").strip()
    raw_model = (model or "").strip()
    if raw_provider == "" or raw_provider == "mock":
        raw_provider = "auto"
    if raw_provider == "auto" and not allow_auto:
        raw_provider = "openrouter"
    if raw_provider != "auto" and raw_provider not in CANONICAL_PROVIDERS:
        raise ValueError(f"Provider không hỗ trợ: {raw_provider}")

    inferred_provider = explicit_provider_from_model(raw_model)
    provider_id = raw_provider
    warning = None
    if inferred_provider:
        inferred_provider = canonical_provider_id(inferred_provider) or inferred_provider
        if raw_provider == "auto":
            provider_id = inferred_provider
            warning = f"Đã suy ra provider {inferred_provider} từ model {raw_model}."
        elif inferred_provider != raw_provider:
            message = f"Model {raw_model} thuộc provider {inferred_provider}, không thể lưu dưới provider {raw_provider}."
            if strict:
                raise ValueError(message)
            provider_id = inferred_provider
            warning = message

    model_id = normalize_model_for_provider(provider_id, raw_model) or ""
    changed = provider_id != raw_provider or model_id != raw_model
    return CanonicalModelRef(provider_id=provider_id, model_id=model_id, changed=changed, warning=warning)


def canonicalize_legacy_model_ref(provider: str | None, model: str | None, *, allow_auto: bool = True) -> CanonicalModelRef:
    return canonicalize_model_ref(provider, model, strict=False, allow_auto=allow_auto)


def canonicalize_fallback_models(provider: str, fallbacks: list[str], *, strict: bool = True) -> tuple[list[str], list[str]]:
    provider_id = canonical_provider_id(provider) or provider
    canonical: list[str] = []
    warnings: list[str] = []
    for fallback in fallbacks:
        if not fallback or not fallback.strip():
            continue
        try:
            ref = canonicalize_model_ref(provider_id, fallback, strict=strict, allow_auto=False)
        except ValueError:
            if strict:
                raise
            warnings.append(f"Bỏ fallback không cùng provider {provider_id}: {fallback}")
            continue
        if ref.provider_id != provider_id or _looks_like_other_provider_model(provider_id, fallback):
            if strict:
                raise ValueError(f"Fallback {fallback} không thuộc provider {provider_id}.")
            warnings.append(f"Bỏ fallback không cùng provider {provider_id}: {fallback}")
            continue
        if ref.model_id not in canonical:
            canonical.append(ref.model_id)
        if ref.warning:
            warnings.append(ref.warning)
    return canonical, warnings


def _looks_like_other_provider_model(provider_id: str, model: str) -> bool:
    inferred = infer_provider_from_model(model)
    if inferred is None:
        return False
    inferred = canonical_provider_id(inferred) or inferred
    return inferred != provider_id


def resolve_ocr_provider(provider: OcrProvider | None, model: str | None) -> OcrProvider:
    if provider is not None:
        return provider
    inferred = infer_provider_from_model(model)
    if inferred in {"router9", "openrouter", "nvidia", "ollama", "openai_compat"}:
        return inferred
    return "openrouter"
