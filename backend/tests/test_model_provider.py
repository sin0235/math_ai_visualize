import pytest
from fastapi import HTTPException

from app.api import routes_ai_models
from app.schemas.scene import AiModelInfo
from app.services.ai_fallback import explicit_model_for_provider
from app.services.ai_providers import ModelListResult
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
        canonicalize_model_ref("nvidia", "openrouter/google/gemma-4-26b-it:free")


@pytest.mark.parametrize("model_id", [
    "nvidia/deepseek-ai/deepseek-v4-flash",
    "ollama/qwen3",
    "openrouter/google/gemma-4-26b-it:free",
])
def test_canonicalize_model_ref_keeps_namespaced_models_for_router9_proxy(model_id):
    ref = canonicalize_model_ref("router9", model_id)

    assert ref.provider_id == "router9"
    assert ref.model_id == model_id


def test_canonicalize_legacy_model_ref_keeps_namespaced_router9_model():
    ref = canonicalize_legacy_model_ref("router9", "openrouter/google/gemma-4-26b-it:free")

    assert ref.provider_id == "router9"
    assert ref.model_id == "openrouter/google/gemma-4-26b-it:free"
    assert ref.warning is None


def test_canonicalize_fallback_models_allows_any_model_for_auto_provider():
    models, warnings = canonicalize_fallback_models("auto", ["openai/gpt-oss-120b:free", "nvidia/nemotron"])

    assert models == ["openai/gpt-oss-120b:free", "nvidia/nemotron"]
    assert warnings == []


def test_canonicalize_fallback_models_keeps_vendor_namespace_for_primary_provider():
    models, warnings = canonicalize_fallback_models("openrouter", ["nvidia/nemotron-3-super-120b-a12b:free"])

    assert models == ["nvidia/nemotron-3-super-120b-a12b:free"]
    assert warnings == []


@pytest.mark.parametrize("model_id", [
    "nvidia/deepseek-ai/deepseek-v4-flash",
    "ollama/qwen3",
    "openrouter/google/gemma",
])
def test_canonicalize_fallback_models_keeps_slash_model_under_primary_provider(model_id):
    models, warnings = canonicalize_fallback_models("router9", [model_id])

    assert models == [model_id]
    assert warnings == []


def test_canonicalize_fallback_models_routes_only_explicit_cross_provider_ref():
    models, warnings = canonicalize_fallback_models("router9", ["ollama::qwen3"])

    assert models == ["ollama::qwen3"]
    assert warnings == []


def test_explicit_model_for_provider_keeps_vendor_namespaces_under_selected_provider():
    assert explicit_model_for_provider("nvidia", "qwen/qwen3-coder-480b-a35b-instruct") == "qwen/qwen3-coder-480b-a35b-instruct"
    assert explicit_model_for_provider("openrouter", "nvidia/nemotron-3-super-120b-a12b:free") == "nvidia/nemotron-3-super-120b-a12b:free"
    assert explicit_model_for_provider("router9", "gh/claude-haiku-4.5") == "gh/claude-haiku-4.5"
    assert explicit_model_for_provider("router9", "nvidia/deepseek-ai/deepseek-v4-flash") == "nvidia/deepseek-ai/deepseek-v4-flash"
    assert explicit_model_for_provider("router9", "ollama/qwen3") == "ollama/qwen3"
    assert explicit_model_for_provider("router9", "openrouter/google/gemma") == "openrouter/google/gemma"


def test_explicit_model_for_provider_rejects_only_app_qualified_mismatch():
    assert explicit_model_for_provider("nvidia", "openrouter/qwen/qwen3-next-80b-a3b-instruct:free") is None
    assert explicit_model_for_provider("openrouter", "router9/cx/gpt-5.5") is None


def test_resolve_ocr_provider_only_infers_app_qualified_prefixes():
    assert resolve_ocr_provider(None, "router9/gh/gpt-5.2") == "router9"
    assert resolve_ocr_provider(None, "openrouter/google/gemini-flash") == "openrouter"
    assert resolve_ocr_provider(None, "gh/gpt-5.2") == "openrouter"
    assert resolve_ocr_provider("router9", "gh/gpt-5.2") == "router9"


@pytest.mark.anyio
async def test_scan_models_keeps_router9_namespaces(monkeypatch):
    async def resolve_settings(db, runtime_settings):
        return object()

    async def list_models(settings, provider):
        return ModelListResult(models=[
            AiModelInfo(id="nvidia/deepseek-ai/deepseek-v4-flash", label="DeepSeek", provider="nvidia"),
            AiModelInfo(id="ollama/qwen3", label="Qwen", provider="ollama"),
            AiModelInfo(id="openrouter/google/gemma", label="Gemma", provider="openrouter"),
        ])

    monkeypatch.setattr(routes_ai_models, "resolve_effective_settings", resolve_settings)
    monkeypatch.setattr(routes_ai_models, "list_provider_models_with_warnings", list_models)

    response = await routes_ai_models._scan_models(object(), None, "router9")

    assert [model.id for model in response.models] == [
        "nvidia/deepseek-ai/deepseek-v4-flash",
        "ollama/qwen3",
        "openrouter/google/gemma",
    ]
    assert {model.provider for model in response.models} == {"router9"}


@pytest.mark.anyio
async def test_scan_models_returns_provider_error_without_secret(monkeypatch):
    async def resolve_settings(db, runtime_settings):
        return object()

    async def fail_scan(settings, provider):
        raise RuntimeError("provider quota exhausted api_key=secret-value")

    monkeypatch.setattr(routes_ai_models, "resolve_effective_settings", resolve_settings)
    monkeypatch.setattr(routes_ai_models, "list_provider_models_with_warnings", fail_scan)

    with pytest.raises(HTTPException) as error:
        await routes_ai_models._scan_models(object(), None, "router9")

    assert error.value.status_code == 502
    assert error.value.detail["code"] == "model_scan_failed"
    assert "provider quota exhausted" in error.value.detail["message"]
    assert "secret-value" not in error.value.detail["message"]


@pytest.mark.anyio
async def test_scan_models_returns_explicit_timeout_error(monkeypatch):
    async def resolve_settings(db, runtime_settings):
        return object()

    async def timeout_scan(settings, provider):
        raise TimeoutError

    monkeypatch.setattr(routes_ai_models, "resolve_effective_settings", resolve_settings)
    monkeypatch.setattr(routes_ai_models, "list_provider_models_with_warnings", timeout_scan)

    with pytest.raises(HTTPException) as error:
        await routes_ai_models._scan_models(object(), None, "router9")

    assert error.value.status_code == 504
    assert error.value.detail["code"] == "model_scan_timeout"
    assert "110 giây" in error.value.detail["message"]


@pytest.mark.anyio
async def test_scan_models_preserves_existing_http_error(monkeypatch):
    expected = HTTPException(status_code=429, detail={"code": "provider_rate_limited", "message": "Provider giới hạn yêu cầu."})

    async def fail_settings(db, runtime_settings):
        raise expected

    monkeypatch.setattr(routes_ai_models, "resolve_effective_settings", fail_settings)

    with pytest.raises(HTTPException) as error:
        await routes_ai_models._scan_models(object(), None, "router9")

    assert error.value is expected
