import httpx
import pytest

from app.core.config import Settings
from app.services.ai_providers import NvidiaAdapter, OpenRouterAdapter, get_provider_adapter, should_send_thinking_payload, _parse_nvidia_preview_catalog_page
from app.services.openrouter_client import OpenRouterClient


async def _async_result(value):
    return value


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
    assert detected.warnings == []


def test_nvidia_detects_preview_nim_type_as_free_endpoint():
    adapter = NvidiaAdapter()

    detected = adapter.detect_capabilities("nvidia/preview", {"id": "nvidia/preview", "nimType": "nim_type_preview"})

    assert detected.is_free_endpoint is True


@pytest.mark.anyio
async def test_openrouter_adapter_lists_only_models_with_free_tag(monkeypatch):
    async def fake_get_openai_models(provider, headers, normalized_base, params=None, url=None):
        assert provider == "openrouter"
        return httpx.Response(200, json={"data": [
            {"id": "cohere/north-mini-code:free", "pricing": {"prompt": "0", "completion": "0"}},
            {"id": "google/paid-model", "pricing": {"prompt": "1", "completion": "2"}},
            {"id": "vendor/free-without-tag", "pricing": {"prompt": "0", "completion": "0"}},
        ]})

    monkeypatch.setattr("app.services.ai_providers._get_openai_models", fake_get_openai_models)

    result = await get_provider_adapter("openrouter").list_models(Settings(_env_file=None, openrouter_api_key="secret"))

    assert [model.id for model in result.models] == ["cohere/north-mini-code:free"]
    assert result.models[0].is_free_endpoint is True
    assert result.warnings == ["Đã bỏ 2 OpenRouter model không có tag :free."]


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


def test_nvidia_preview_catalog_parser_reads_rsc_page_resources():
    slugs, total_pages = _parse_nvidia_preview_catalog_page('''
        {"resultPageTotal":4,"resultTotal":76,"resources":[
          {"resourceId":"org/page-three-model"},
          {"resourceId":"org/cosmos-transfer2_5-2b"}
        ]}
    ''')

    assert total_pages == 4
    assert slugs == {"page-three-model", "cosmos-transfer2_5-2b"}


def test_nvidia_preview_catalog_parser_falls_back_to_html_links():
    slugs, total_pages = _parse_nvidia_preview_catalog_page('''
        <a href="/nvidia/glm-5_2">glm</a>
        <a href="/explore/discover">Explore</a>
    ''')

    assert total_pages is None
    assert slugs == {"glm-5_2"}


@pytest.mark.anyio
async def test_openrouter_client_explicit_thinking_requires_known_capability(monkeypatch):
    payloads = []

    async def fake_collect(client, url, headers, payload, timeout):
        payloads.append(payload)
        return '{}', 2, None

    monkeypatch.setattr("app.services.http_pool.get_client", lambda *args, **kwargs: object())
    monkeypatch.setattr("app.services.openrouter_client.collect_openai_chat_stream", fake_collect)

    settings = Settings(_env_file=None, openrouter_api_key="secret")
    await OpenRouterClient(settings, model="plain", reasoning_enabled=True, supports_thinking=None).extract_scene_json("x")
    await OpenRouterClient(settings, model="thinking", reasoning_enabled=True, supports_thinking=True).extract_scene_json("x")

    assert "reasoning" not in payloads[0]
    assert payloads[1]["reasoning"] == {"enabled": True}


@pytest.mark.anyio
async def test_nvidia_adapter_lists_models_with_capabilities(monkeypatch):
    async def fake_get_openai_models(provider, headers, normalized_base, params=None, url=None):
        assert provider == "nvidia"
        assert headers["Authorization"] == "Bearer nvidia-secret"
        assert normalized_base == "https://integrate.api.nvidia.com/v1"
        return httpx.Response(200, json={"data": [
            {
                "id": "nvidia/vision",
                "owned_by": "nvidia",
                "nimType": "nim_type_preview",
                "capabilities": {"supports_vision": True},
                "supported_parameters": ["thinking"],
            },
            {
                "id": "nvidia/page-three-model",
                "owned_by": "nvidia",
                "supported_parameters": ["temperature"],
            },
            {
                "id": "nvidia/cosmos-transfer2.5-2b",
                "owned_by": "nvidia",
                "supported_parameters": ["temperature"],
            },
            {
                "id": "nvidia/not-free",
                "owned_by": "nvidia",
                "supported_parameters": ["temperature"],
            },
        ]})

    monkeypatch.setattr("app.services.ai_providers._get_openai_models", fake_get_openai_models)
    monkeypatch.setattr("app.services.ai_providers._fetch_nvidia_preview_model_slugs", lambda: _async_result(({"vision", "page-three-model", "cosmos-transfer2_5-2b"}, None)))

    result = await get_provider_adapter("nvidia").list_models(Settings(_env_file=None, nvidia_api_key="nvidia-secret"))

    assert result.warnings == [
        "Đã bỏ 1 NVIDIA model không thuộc Free Endpoint. "
        "Nguồn lọc: https://build.nvidia.com/models?filters=nimType%3Anim_type_preview"
    ]
    assert len(result.models) == 3
    by_id = {model.id: model for model in result.models}
    assert "nvidia/cosmos-transfer2.5-2b" in by_id
    model = by_id["nvidia/vision"]
    assert model.is_free_endpoint is True
    assert model.supports_thinking is True
    assert model.supports_vision is True
    assert model.endpoint_metadata["owned_by"] == "nvidia"
    catalog_model = by_id["nvidia/page-three-model"]
    assert catalog_model.is_free_endpoint is True
    assert catalog_model.endpoint_metadata["nvidia_free_endpoint_source"] == "https://build.nvidia.com/models?filters=nimType%3Anim_type_preview"


@pytest.mark.anyio
async def test_nvidia_adapter_warns_when_preview_catalog_fails(monkeypatch):
    async def fake_get_openai_models(provider, headers, normalized_base, params=None, url=None):
        return httpx.Response(200, json={"data": [
            {"id": "nvidia/metadata-free", "nimType": "nim_type_preview"},
            {"id": "nvidia/catalog-only"},
        ]})

    monkeypatch.setattr("app.services.ai_providers._get_openai_models", fake_get_openai_models)
    monkeypatch.setattr(
        "app.services.ai_providers._fetch_nvidia_preview_model_slugs",
        lambda: _async_result((set(), "Không đọc được NVIDIA Free Endpoint catalog; chỉ dùng metadata trong /v1/models để lọc.")),
    )

    result = await get_provider_adapter("nvidia").list_models(Settings(_env_file=None, nvidia_api_key="nvidia-secret"))

    assert [model.id for model in result.models] == ["nvidia/metadata-free"]
    assert result.warnings == [
        "Không đọc được NVIDIA Free Endpoint catalog; chỉ dùng metadata trong /v1/models để lọc.",
        "Đã bỏ 1 NVIDIA model không thuộc Free Endpoint. Nguồn lọc: metadata Free Endpoint/nim_type_preview",
    ]


@pytest.mark.anyio
async def test_router9_adapter_lists_all_paginated_llm_models_only(monkeypatch):
    calls: list[tuple[str, dict[str, str] | None]] = []

    async def fake_get_openai_models(provider, headers, normalized_base, params=None, url=None):
        assert provider == "router9"
        assert headers["Authorization"] == "Bearer router-secret"
        path = url.removeprefix(normalized_base)
        calls.append((path, params))
        assert path == "/models"
        if params is None:
            return httpx.Response(200, json={
                "object": "list",
                "data": [
                    {"id": "vendor/model-without-capability"},
                    {"id": "router/vision", "capabilities": {"vision": True}},
                ],
                "next_cursor": "page-2",
            })
        assert params == {"cursor": "page-2"}
        return httpx.Response(200, json={
            "object": "list",
            "data": [
                {"id": "router/reasoning", "supported_parameters": ["thinking"]},
                {"id": "router/vision", "capabilities": {"vision": True}},
            ],
        })

    monkeypatch.setattr("app.services.ai_providers._get_openai_models", fake_get_openai_models)

    result = await get_provider_adapter("router9").list_models(Settings(
        _env_file=None,
        router9_api_key="router-secret",
        router9_base_url="https://router.example/v1",
    ))

    assert calls == [
        ("/models", None),
        ("/models", {"cursor": "page-2"}),
    ]
    assert [model.id for model in result.models] == [
        "router/reasoning",
        "router/vision",
        "vendor/model-without-capability",
    ]
    assert all(model.endpoint_metadata["service_kind"] == "llm" for model in result.models)
    assert result.models[0].supports_thinking is True
    assert result.models[1].supports_vision is True
    assert result.warnings == []
