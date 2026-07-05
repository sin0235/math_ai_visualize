import httpx
import pytest

from app.core.config import Settings
from app.services.ai_providers import NvidiaAdapter, OpenRouterAdapter, get_provider_adapter, should_send_thinking_payload


def test_openrouter_detects_free_thinking_vision_from_metadata():
    adapter = OpenRouterAdapter()

    detected = adapter.detect_capabilities("google/gemma:free", {
        "id": "google/gemma:free",
        "supported_parameters": ["reasoning_effort", "temperature"],
        "pricing": {"prompt": "0", "completion": "0"},
        "input_modalities": ["text", "image"],
        "context_length": 32768,
    })

    assert detected.is_free_endpoint is True
    assert detected.supports_thinking is True
    assert detected.supports_vision is True
    assert detected.supported_parameters == ["reasoning_effort", "temperature"]
    assert detected.pricing == {"completion": "0", "prompt": "0"}
    assert detected.context_length == 32768


def test_nvidia_free_endpoint_stays_false_without_explicit_metadata():
    adapter = NvidiaAdapter()

    detected = adapter.detect_capabilities("qwen/model", {"id": "qwen/model", "supported_parameters": ["temperature"]})

    assert detected.is_free_endpoint is False
    assert detected.supports_thinking is False
    assert detected.warnings == ["NVIDIA model qwen/model chưa có metadata free endpoint rõ ràng."]


def test_openrouter_chat_payload_gates_reasoning_by_capability():
    adapter = OpenRouterAdapter()
    messages = [{"role": "user", "content": "x"}]

    disabled = adapter.build_chat_payload(
        "openrouter/plain-model",
        messages,
        request_thinking=True,
        supports_thinking=False,
        allow_unknown_thinking=True,
    )
    enabled = adapter.build_chat_payload(
        "openrouter/thinking-model",
        messages,
        request_thinking=True,
        supports_thinking=True,
    )

    assert disabled == {"model": "plain-model", "messages": messages}
    assert enabled["reasoning"] == {"enabled": True}


def test_unknown_thinking_payload_requires_explicit_unknown_allowance():
    assert should_send_thinking_payload(request_thinking=True, supports_thinking=None, allow_unknown_thinking=False) is False
    assert should_send_thinking_payload(request_thinking=True, supports_thinking=None, allow_unknown_thinking=True) is True


def test_nvidia_chat_payload_uses_provider_specific_thinking_param():
    payload = NvidiaAdapter().build_chat_payload(
        "qwen/model",
        [{"role": "user", "content": "x"}],
        request_thinking=True,
        supports_thinking=True,
        supported_parameters=["thinking"],
    )

    assert payload["chat_template_kwargs"] == {"thinking": True}


@pytest.mark.anyio
async def test_nvidia_adapter_lists_models_with_capabilities(monkeypatch):
    async def fake_get_openai_models(provider, headers, normalized_base, params=None, url=None):
        assert provider == "nvidia"
        assert headers["Authorization"] == "Bearer nvidia-secret"
        assert normalized_base == "https://integrate.api.nvidia.com/v1"
        return httpx.Response(200, json={"data": [{
            "id": "nvidia/vision",
            "owned_by": "nvidia",
            "free": True,
            "capabilities": {"supports_vision": True},
            "supported_parameters": ["thinking"],
        }]})

    monkeypatch.setattr("app.services.ai_providers._get_openai_models", fake_get_openai_models)

    result = await get_provider_adapter("nvidia").list_models(Settings(_env_file=None, nvidia_api_key="nvidia-secret"))

    assert result.warnings == []
    assert len(result.models) == 1
    model = result.models[0]
    assert model.id == "nvidia/vision"
    assert model.is_free_endpoint is True
    assert model.supports_thinking is True
    assert model.supports_vision is True
    assert model.endpoint_metadata["owned_by"] == "nvidia"