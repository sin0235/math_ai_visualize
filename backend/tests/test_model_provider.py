import pytest

from app.services.ai_fallback import explicit_model_for_provider
from app.services.model_provider import canonicalize_fallback_models, canonicalize_legacy_model_ref, canonicalize_model_ref, normalize_provider_defaults, resolve_ocr_provider


def test_canonicalize_model_ref_strips_matching_provider_prefix():
    ref = canonicalize_model_ref("openrouter", "openrouter/google/gemma-4-26b-it:free")

    assert ref.provider_id == "openrouter"
    assert ref.model_id == "google/gemma-4-26b-it:free"
    assert ref.changed is True


def test_canonicalize_model_ref_infers_auto_provider_from_explicit_model_prefix():
    ref = canonicalize_model_ref("auto", "openrouter/google/gemma-4-26b-it:free")

    assert ref.provider_id == "openrouter"
    assert ref.model_id == "google/gemma-4-26b-it:free"
    assert ref.warning


def test_canonicalize_model_ref_does_not_treat_vendor_namespace_as_provider_prefix():
    ref = canonicalize_model_ref("openrouter", "nvidia/llama-3.3-nemotron-super-49b-v1.5")

    assert ref.provider_id == "openrouter"
    assert ref.model_id == "nvidia/llama-3.3-nemotron-super-49b-v1.5"


def test_normalize_provider_defaults_keeps_openrouter_vendor_namespaces():
    value = normalize_provider_defaults({
        "openrouter": {
            "model": "nvidia/nemotron-3-super-120b-a12b:free",
            "scanned_models": [
                {"id": "nvidia/nemotron-3-super-120b-a12b:free", "label": "Nemotron", "provider": "openrouter"},
                {"id": "openai/gpt-oss-120b:free", "label": "GPT OSS", "provider": "openrouter"},
            ],
            "allowed_model_ids": ["nvidia/nemotron-3-super-120b-a12b:free", "openai/gpt-oss-120b:free"],
        }
    })

    assert value["openrouter"]["model"] == "nvidia/nemotron-3-super-120b-a12b:free"
    assert value["openrouter"]["allowed_model_ids"] == ["nvidia/nemotron-3-super-120b-a12b:free", "openai/gpt-oss-120b:free"]
    assert [model["id"] for model in value["openrouter"]["scanned_models"]] == ["nvidia/nemotron-3-super-120b-a12b:free", "openai/gpt-oss-120b:free"]


def test_canonicalize_model_ref_rejects_provider_model_mismatch():
    with pytest.raises(ValueError, match="thuộc provider openrouter"):
        canonicalize_model_ref("router9", "openrouter/google/gemma-4-26b-it:free")


def test_canonicalize_legacy_model_ref_repairs_provider_model_mismatch():
    ref = canonicalize_legacy_model_ref("router9", "openrouter/google/gemma-4-26b-it:free")

    assert ref.provider_id == "openrouter"
    assert ref.model_id == "google/gemma-4-26b-it:free"
    assert ref.warning


def test_canonicalize_fallback_models_allows_any_model_for_auto_provider():
    models, warnings = canonicalize_fallback_models("auto", ["openai/gpt-oss-120b:free", "nvidia/nemotron"])

    assert models == ["openai/gpt-oss-120b:free", "nvidia/nemotron"]
    assert warnings == []


def test_canonicalize_fallback_models_keeps_vendor_namespace_for_primary_provider():
    models, warnings = canonicalize_fallback_models("openrouter", ["nvidia/nemotron-3-super-120b-a12b:free"])

    assert models == ["nvidia/nemotron-3-super-120b-a12b:free"]
    assert warnings == []


def test_canonicalize_fallback_models_keeps_cross_provider_fallbacks():
    models, warnings = canonicalize_fallback_models("router9", ["router9/cc/codex-5.5-image", "openrouter/google/gemma"])

    assert models == ["cc/codex-5.5-image", "openrouter/google/gemma"]
    assert warnings == []


def test_explicit_model_for_provider_keeps_vendor_namespaces_under_selected_provider():
    assert explicit_model_for_provider("nvidia", "qwen/qwen3-coder-480b-a35b-instruct") == "qwen/qwen3-coder-480b-a35b-instruct"
    assert explicit_model_for_provider("openrouter", "nvidia/nemotron-3-super-120b-a12b:free") == "nvidia/nemotron-3-super-120b-a12b:free"
    assert explicit_model_for_provider("router9", "gh/claude-haiku-4.5") == "gh/claude-haiku-4.5"


def test_explicit_model_for_provider_rejects_only_app_qualified_mismatch():
    assert explicit_model_for_provider("nvidia", "openrouter/qwen/qwen3-next-80b-a3b-instruct:free") is None
    assert explicit_model_for_provider("openrouter", "router9/cx/gpt-5.5") is None


def test_resolve_ocr_provider_only_infers_app_qualified_prefixes():
    assert resolve_ocr_provider(None, "router9/gh/gpt-5.2") == "router9"
    assert resolve_ocr_provider(None, "openrouter/google/gemini-flash") == "openrouter"
    assert resolve_ocr_provider(None, "gh/gpt-5.2") == "openrouter"
    assert resolve_ocr_provider("router9", "gh/gpt-5.2") == "router9"
