from dataclasses import dataclass

from app.schemas.scene import OcrProvider


CANONICAL_PROVIDERS = {"local", "openrouter", "nvidia", "ollama", "openai_compat", "router9"}
REGISTRY_PROVIDERS = ("openrouter", "nvidia", "ollama", "openai_compat", "router9")



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
    "nvidia": ("nvidia/",),
    "ollama": ("ollama/",),
    "openai_compat": ("openai_compat/", "openai-compat/"),
}
PROVIDER_MODEL_REF_SEPARATOR = "::"


def format_provider_model_ref(provider: str, model: str) -> str:
    provider_id = canonical_provider_id(provider) or provider
    model_id = normalize_model_for_provider(provider_id, model) or ""
    return f"{provider_id}{PROVIDER_MODEL_REF_SEPARATOR}{model_id}" if provider_id and model_id else ""


def parse_provider_model_ref(value: str | None, *, allow_legacy_slash: bool = False) -> CanonicalModelRef | None:
    model_ref = (value or "").strip()
    if not model_ref:
        return None
    if PROVIDER_MODEL_REF_SEPARATOR in model_ref:
        provider_id, model_id = model_ref.split(PROVIDER_MODEL_REF_SEPARATOR, 1)
        provider_id = canonical_provider_id(provider_id.strip()) or ""
        model_id = model_id.strip()
        if not provider_id or provider_id not in CANONICAL_PROVIDERS or not model_id:
            raise ValueError(f"Model ref không hợp lệ: {model_ref}")
        normalized_model = normalize_model_for_provider(provider_id, model_id) or ""
        return CanonicalModelRef(provider_id=provider_id, model_id=normalized_model, changed=model_ref != format_provider_model_ref(provider_id, normalized_model))
    if not allow_legacy_slash:
        return None
    for provider_id, prefixes in EXPLICIT_PROVIDER_PREFIXES.items():
        for prefix in prefixes:
            if model_ref.startswith(prefix):
                model_id = model_ref.removeprefix(prefix).strip()
                if not model_id:
                    raise ValueError(f"Model ref không hợp lệ: {model_ref}")
                return CanonicalModelRef(provider_id=provider_id, model_id=model_id, changed=True)
    return None


def canonical_provider_id(provider: str | None) -> str | None:
    if provider is None:
        return None
    return provider.strip()


def normalize_provider_defaults(value: dict | None) -> dict | None:
    if value is None:
        return None
    normalized = dict(value)
    for provider_id in REGISTRY_PROVIDERS:
        provider = normalized.get(provider_id)
        if not isinstance(provider, dict):
            continue
        provider_normalized = dict(provider)
        # Retired fields: provider-level default model is task-profile authority now.
        provider_normalized.pop("model", None)
        provider_normalized.pop("default_model_id", None)
        if provider_id != "router9":
            provider_normalized.pop("only_mode", None)
        scanned = provider_normalized.get("scanned_models")
        if isinstance(scanned, list):
            provider_normalized["scanned_models"] = [model for model in scanned if _model_belongs_to_provider(provider_id, _model_id_from_item(model))]
        allowed = provider_normalized.get("allowed_model_ids")
        if isinstance(allowed, list):
            provider_normalized["allowed_model_ids"] = [str(model_id) for model_id in allowed if _model_belongs_to_provider(provider_id, str(model_id))]
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
    try:
        ref = parse_provider_model_ref(model_id, allow_legacy_slash=False)
    except ValueError:
        return False
    return ref is None or ref.provider_id == provider_id


def canonicalize_explicit_provider_model(provider: str, model: str | None, *, allow_auto: bool = False) -> CanonicalModelRef:
    provider_id = canonical_provider_id(provider) or "auto"
    model_id = (model or "").strip()
    if provider_id == "" or provider_id == "mock":
        provider_id = "auto"
    if provider_id == "auto" and not allow_auto:
        raise ValueError("Model cụ thể phải đi kèm provider rõ ràng.")
    if provider_id != "auto" and provider_id not in CANONICAL_PROVIDERS:
        raise ValueError(f"Provider không hỗ trợ: {provider_id}")
    explicit_ref = parse_provider_model_ref(model_id, allow_legacy_slash=False)
    if explicit_ref is not None:
        if explicit_ref.provider_id != provider_id:
            raise ValueError(f"Model {model_id} thuộc provider {explicit_ref.provider_id}, không thể lưu dưới provider {provider_id}.")
        model_id = explicit_ref.model_id
    normalized_model = normalize_model_for_provider(provider_id, model_id) or ""
    return CanonicalModelRef(provider_id=provider_id, model_id=normalized_model, changed=provider_id != provider or normalized_model != (model or ""))


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
    if raw_provider == "router9" or (raw_provider == "openrouter" and inferred_provider == "nvidia"):
        inferred_provider = None
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
        model_id = (fallback or "").strip()
        if not model_id:
            continue
        explicit_ref = parse_provider_model_ref(model_id, allow_legacy_slash=False)
        if explicit_ref is not None:
            fallback_id = explicit_ref.model_id if explicit_ref.provider_id == provider_id else format_provider_model_ref(explicit_ref.provider_id, explicit_ref.model_id)
        else:
            fallback_id = normalize_model_for_provider(provider_id, model_id) or ""
        if fallback_id and fallback_id not in canonical:
            canonical.append(fallback_id)
    return canonical, warnings


def resolve_ocr_provider(provider: OcrProvider | None, model: str | None) -> OcrProvider:
    if provider is not None:
        return provider
    explicit_provider = explicit_provider_from_model(model)
    if explicit_provider in {"local", "router9", "openrouter", "ollama", "openai_compat"}:
        return explicit_provider
    return "openrouter"
