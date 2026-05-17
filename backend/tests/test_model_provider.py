import pytest

from app.services.model_provider import canonicalize_fallback_models, canonicalize_legacy_model_ref, canonicalize_model_ref, normalize_provider_defaults


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


def test_canonicalize_fallback_models_rejects_cross_provider_fallback():
    with pytest.raises(ValueError, match="thuộc provider openrouter"):
        canonicalize_fallback_models("router9", ["cc/codex-5.5-image", "openrouter/google/gemma"])


def test_canonicalize_fallback_models_lenient_drops_cross_provider_fallback():
    models, warnings = canonicalize_fallback_models("router9", ["router9/cc/codex-5.5-image", "openrouter/google/gemma"], strict=False)

    assert models == ["cc/codex-5.5-image"]
    assert warnings
