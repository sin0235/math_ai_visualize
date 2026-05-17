import pytest

from app.services.model_provider import canonicalize_fallback_models, canonicalize_legacy_model_ref, canonicalize_model_ref


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
    ref = canonicalize_model_ref("nvidia", "qwen/qwen3-coder-480b-a35b-instruct")

    assert ref.provider_id == "nvidia"
    assert ref.model_id == "qwen/qwen3-coder-480b-a35b-instruct"


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
