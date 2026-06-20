from dataclasses import dataclass

from app.schemas.scene import OcrProvider


CANONICAL_PROVIDERS = {"local", "openrouter", "nvidia", "ollama", "openai_compat", "router9"}
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


EXPLICIT_PROVIDER_PREFIXES = {
    "local": ("local/",),
    "router9": ("router9/",),
    "openrouter": ("openrouter/",),
    "ollama": ("ollama/",),
    "openai_compat": ("openai_compat/", "openai-compat/"),
}


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
        scanned = provider_normalized.get("scanned_models")
        if isinstance(scanned, list):
            provider_normalized["scanned_models"] = [model for model in scanned if _model_belongs_to_provider(provider_id, _model_id_from_item(model))]
        allowed = provider_normalized.get("allowed_model_ids")
        if isinstance(allowed, list):
            provider_normalized["allowed_model_ids"] = [str(model_id) for model_id in allowed if _model_belongs_to_provider(provider_id, str(model_id))]
        allowed = provider_normalized.get("allowed_model_ids")
        model = provider_normalized.get("model")
        if isinstance(model, str) and model and not _model_belongs_to_provider(provider_id, model):
            provider_normalized["model"] = ""
            model = ""
        if isinstance(allowed, list) and allowed and isinstance(model, str) and model and model not in allowed:
            provider_normalized["model"] = str(allowed[0])
        normalized[provider_id] = provider_normalized
    return normalized


def _model_id_from_item(model: object) -> str:
    if isinstance(model, str):
        return model
    if isinstance(model, dict):
        value = model.get("id")
        return value if isinstance(value, str) else ""
    return ""


def _model_belongs_to_provider(provider_id: str, model_id: str) -> bool:
    inferred = explicit_provider_from_model(model_id)
    return inferred is None or inferred == provider_id


def normalize_model_for_provider(provider: str, model: str | None) -> str | None:
    provider = canonical_provider_id(provider) or provider
    if provider == "local" and model:
        return model.removeprefix("local/")
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
    if provider_id == "auto":
        for fallback in fallbacks:
            model_id = (fallback or "").strip()
            if model_id and model_id not in canonical:
                canonical.append(model_id)
        return canonical, warnings
    for fallback in fallbacks:
        if not fallback or not fallback.strip():
            continue
        ref = canonicalize_model_ref(provider_id, fallback, strict=False, allow_auto=False)
        fallback_id = ref.model_id if ref.provider_id == provider_id else f"{ref.provider_id}/{ref.model_id}"
        if fallback_id not in canonical:
            canonical.append(fallback_id)
        if ref.warning and not fallback_id.startswith(f"{ref.provider_id}/"):
            warnings.append(ref.warning)
    return canonical, warnings


def resolve_ocr_provider(provider: OcrProvider | None, model: str | None) -> OcrProvider:
    if provider is not None:
        return provider
    explicit_provider = explicit_provider_from_model(model)
    if explicit_provider in {"local", "router9", "openrouter", "ollama", "openai_compat"}:
        return explicit_provider
    return "openrouter"
