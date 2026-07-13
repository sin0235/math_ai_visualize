import asyncio
import json
import logging

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.deps import require_active_user
from app.core.config import Settings, get_settings, merge_runtime_settings
from app.db.migrations import apply_sqlite_migrations
from app.db.models import UserRecord
from app.db.session import SQLiteClient, get_database
from app.main import app
from app.schemas.scene import AiModelInfo, OcrRequest, RenderRequest, RuntimeSettings
from app.services.extractor import extract_scene, _provider_order
from app.services.openai_compat_client import OpenAICompatClient
from app.services.openrouter_client import OpenRouterClient
from app.services.provider_logging import format_provider_error, redact_sensitive
from app.services.provider_ping import check_provider_connection
from app.services.solver_explainer import _call_explainer
from app.services.router9_bootstrap import (
    bootstrap_router9_models,
    select_codex_model_ids,
    select_router9_ocr_model_ids,
    select_router9_render_model_ids,
)
from app.services.router9_client import Router9Client


def test_http_pool_close_all_closes_async_clients():
    from app.services import http_pool

    client = http_pool.get_client("https://example.test")

    assert client.is_closed is False
    asyncio.run(http_pool.close_all())
    assert client.is_closed is True
    assert http_pool._pool == {}


def test_render_request_accepts_new_ai_providers():
    base = {"problem_text": "test", "preferred_ai_provider": "openrouter"}
    assert RenderRequest.model_validate(base).preferred_ai_provider == "openrouter"

    base["preferred_ai_provider"] = "ollama"
    assert RenderRequest.model_validate(base).preferred_ai_provider == "ollama"

    base["preferred_ai_provider"] = "ollama"
    assert RenderRequest.model_validate(base).preferred_ai_provider == "ollama"

    base["preferred_ai_provider"] = "router9"
    base["preferred_ai_model"] = "provider/model"
    request = RenderRequest.model_validate(base)
    assert request.preferred_ai_provider == "router9"
    assert request.preferred_ai_model == "provider/model"


def test_request_schemas_reject_large_user_inputs():
    too_long_problem = "x" * 20_001
    too_long_image_url = "x" * 12_000_001

    for schema, payload in [
        (RenderRequest, {"problem_text": too_long_problem}),
        (OcrRequest, {"image_data_url": too_long_image_url}),
        (RuntimeSettings, {"openrouter": {"api_key": "x" * 4_097}}),
        (RuntimeSettings, {"openrouter": {"base_url": "x" * 2_049}}),
        (RuntimeSettings, {"openrouter": {"model": "x" * 513}}),
    ]:
        try:
            schema.model_validate(payload)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected {schema.__name__} to reject oversized payload")


def test_provider_error_redaction_removes_secrets_and_image_data():
    response = httpx.Response(
        400,
        json={
            "error": {
                "message": "Authorization Bearer secret-token api_key=secret-key data:image/png;base64,aGVsbG8=",
                "api_key": "secret-key",
            }
        },
    )

    message = format_provider_error("Test", response)
    redacted = redact_sensitive("token=abc data:image/png;base64,aGVsbG8=")

    assert "secret-token" not in message
    assert "secret-key" not in message
    assert "aGVsbG8=" not in message
    assert "abc" not in redacted
    assert "data:image/[REDACTED]" in message


def test_chat_message_input_chars_counts_prompt_and_multimodal_content():
    from app.services.provider_logging import chat_message_input_chars

    messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "user prompt"},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "ocr hint"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,abcd"}},
            ],
        },
    ]

    assert chat_message_input_chars(messages) == len("system prompt") + len("user prompt") + len("ocr hint") + len("data:image/png;base64,abcd")


def test_openai_compat_request_logs_full_input_chars(monkeypatch):
    captured = {}

    class FakeClient:
        async def post(self, url, headers, json, timeout):
            captured["payload"] = json
            return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    def fake_log_provider_request(provider, kind, url, model, **metadata):
        captured["metadata"] = metadata

    monkeypatch.setattr("app.services.http_pool.get_client", lambda *args: FakeClient())
    monkeypatch.setattr("app.services.openai_compat_client.log_provider_request", fake_log_provider_request)

    asyncio.run(
        OpenAICompatClient(
            Settings(_env_file=None, openai_compat_base_url="https://compat.test/v1", openai_compat_text_model="test-model", openai_compat_api_key="secret")
        )._post_chat(
            {
                "model": "test-model",
                "messages": [
                    {"role": "system", "content": "system prompt"},
                    {"role": "user", "content": "wrapped problem"},
                ],
            },
            "scene",
            problem_chars=len("problem"),
        )
    )

    assert captured["metadata"]["problem_chars"] == len("problem")
    assert captured["metadata"]["input_chars"] == len("system prompt") + len("wrapped problem")


def test_openai_compat_scene_payload_limits_output_and_requests_json(monkeypatch):
    captured = {}

    async def fake_post_chat(self, payload, kind, **log_kwargs):
        captured["payload"] = payload
        captured["kind"] = kind
        return '{"problem_text":"x","renderer":"geogebra_2d","objects":[],"view":{"dimension":"2d"}}'

    monkeypatch.setattr(OpenAICompatClient, "_post_chat", fake_post_chat)

    scene_json = asyncio.run(
        OpenAICompatClient(
            Settings(_env_file=None, openai_compat_base_url="https://compat.test/v1", openai_compat_text_model="test-model", openai_compat_api_key="secret")
        ).extract_scene_json("x")
    )

    assert scene_json["renderer"] == "geogebra_2d"
    assert captured["kind"] == "scene"
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["max_tokens"] == 8192
    assert captured["payload"]["response_format"] == {"type": "json_object"}


def test_openrouter_runtime_skips_reasoning_for_known_non_thinking_model(monkeypatch):
    captured = {}

    class FakeClient:
        async def post(self, url, headers, json, timeout):
            captured["payload"] = json
            return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    monkeypatch.setattr("app.services.http_pool.get_client", lambda *args, **kwargs: FakeClient())

    asyncio.run(
        OpenRouterClient(
            Settings(_env_file=None, openrouter_api_key="secret", openrouter_reasoning_enabled=True),
            model="plain-model",
            supports_thinking=False,
        ).reason_about_problem("Vẽ điểm A")
    )

    assert "reasoning" not in captured["payload"]


def test_openrouter_runtime_sends_reasoning_for_known_thinking_model(monkeypatch):
    captured = {}

    class FakeClient:
        async def post(self, url, headers, json, timeout):
            captured["payload"] = json
            return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    monkeypatch.setattr("app.services.http_pool.get_client", lambda *args, **kwargs: FakeClient())

    asyncio.run(
        OpenRouterClient(
            Settings(_env_file=None, openrouter_api_key="secret", openrouter_reasoning_enabled=True),
            model="thinking-model",
            supports_thinking=True,
        ).reason_about_problem("Vẽ điểm A")
    )

    assert captured["payload"]["reasoning"] == {"enabled": True}


def test_openrouter_runtime_preserves_reasoning_for_unknown_model_with_global_policy(monkeypatch):
    captured = {}

    class FakeClient:
        async def post(self, url, headers, json, timeout):
            captured["payload"] = json
            return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    monkeypatch.setattr("app.services.http_pool.get_client", lambda *args, **kwargs: FakeClient())

    asyncio.run(
        OpenRouterClient(
            Settings(_env_file=None, openrouter_api_key="secret", openrouter_reasoning_enabled=True),
            model="unknown-model",
        ).reason_about_problem("Vẽ điểm A")
    )

    assert captured["payload"]["reasoning"] == {"enabled": True}


def test_openai_compat_recovers_non_json_sse_response(monkeypatch):
    captured = {}

    class FakeClient:
        async def post(self, url, headers, json, timeout):
            captured["payload"] = json
            stream = "\n".join([
                'data: {"choices":[{"delta":{"content":"OK"}}]}',
                "data: [DONE]",
            ])
            return httpx.Response(200, content=stream.encode("utf-8"), headers={"Content-Type": "text/event-stream"})

    monkeypatch.setattr("app.services.http_pool.get_client", lambda *args, **kwargs: FakeClient())

    result = asyncio.run(
        OpenAICompatClient(
            Settings(_env_file=None, openai_compat_base_url="https://compat.test/v1", openai_compat_text_model="test-model", openai_compat_api_key="secret")
        )._post_chat(
            {
                "model": "test-model",
                "messages": [{"role": "user", "content": "Reply with OK only."}],
                "stream": False,
            },
            "check",
        )
    )

    assert result == "OK"
    assert captured["payload"]["stream"] is False


def test_openai_compat_invalid_scene_json_logs_parse_error(monkeypatch):
    captured = {}

    class FakeClient:
        async def post(self, url, headers, json, timeout):
            return httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]})

    def fake_log_parse_error(kind, model, message, response_chars=None):
        captured["parse_error"] = {
            "kind": kind,
            "model": model,
            "message": message,
            "response_chars": response_chars,
        }

    monkeypatch.setattr("app.services.http_pool.get_client", lambda *args, **kwargs: FakeClient())
    monkeypatch.setattr("app.services.openai_compat_client._log_openai_compat_parse_error", fake_log_parse_error)

    with pytest.raises(RuntimeError, match="OpenAI-compatible trả về JSON không hợp lệ"):
        asyncio.run(
            OpenAICompatClient(
                Settings(_env_file=None, openai_compat_base_url="https://compat.test/v1", openai_compat_text_model="test-model", openai_compat_api_key="secret")
            ).extract_scene_json("Vẽ điểm A")
        )

    assert captured["parse_error"]["kind"] == "scene"
    assert captured["parse_error"]["model"] == "test-model"
    assert captured["parse_error"]["message"].startswith("invalid_json:")
    assert captured["parse_error"]["response_chars"] == len("not json")


def test_router9_reasoning_request_logs_reasoning_kind_and_input_chars(monkeypatch):
    captured = {}

    class FakeClient:
        async def post(self, url, headers, json, timeout):
            captured["payload"] = json
            return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    def fake_log_provider_request(provider, kind, url, model, **metadata):
        captured["kind"] = kind
        captured["metadata"] = metadata

    monkeypatch.setattr("app.services.http_pool.get_client", lambda *args: FakeClient())
    monkeypatch.setattr("app.services.router9_client.log_provider_request", fake_log_provider_request)

    asyncio.run(
        Router9Client(
            Settings(_env_file=None, router9_base_url="https://router9.test/v1", router9_api_key="secret", router9_text_model="test-model")
        ).reason_about_problem("Vẽ điểm A", grade=10)
    )

    assert captured["kind"] == "reasoning"
    assert captured["metadata"]["input_chars"] > len("Vẽ điểm A")


def test_openai_compat_provider_check_uses_small_chat_payload(monkeypatch):
    captured = {}

    async def fake_post_chat(self, payload, kind, **log_kwargs):
        captured["payload"] = payload
        captured["kind"] = kind
        captured["log_kwargs"] = log_kwargs
        return "OK"

    monkeypatch.setattr(OpenAICompatClient, "_post_chat", fake_post_chat)

    result = asyncio.run(
        OpenAICompatClient(
            Settings(_env_file=None, openai_compat_base_url="https://compat.test/v1", openai_compat_text_model="test-model")
        ).check_connection()
    )

    assert result == "OK"
    assert captured["kind"] == "check"
    assert captured["payload"]["model"] == "test-model"
    assert captured["payload"]["max_tokens"] == 16
    assert "Vẽ điểm" not in json.dumps(captured["payload"], ensure_ascii=False)


def test_provider_ping_uses_small_chat_payload(monkeypatch):
    captured = {}

    class FakeClient:
        async def post(self, url, headers, json, timeout):
            captured["url"] = url
            captured["headers"] = headers
            captured["payload"] = json
            captured["timeout"] = timeout
            return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    monkeypatch.setattr("app.services.http_pool.get_client", lambda *args: FakeClient())

    model = asyncio.run(
        check_provider_connection(
            "openrouter",
            Settings(_env_file=None, openrouter_api_key="secret", openrouter_text_model="openrouter/test-model"),
        )
    )

    assert model == "openrouter/test-model"
    assert captured["payload"]["model"] == "test-model"
    assert captured["payload"]["max_tokens"] == 16
    assert "Vẽ điểm" not in json.dumps(captured["payload"], ensure_ascii=False)


def test_provider_order_auto_skips_remote_providers_without_api_keys():
    order = _provider_order(Settings(_env_file=None, ai_provider="auto"))

    assert order == ["ollama"]


def test_provider_order_auto_skips_whitespace_api_keys():
    order = _provider_order(
        Settings(
            _env_file=None,
            ai_provider="auto",
            router9_api_key=" ",
            openrouter_api_key="\t",
            nvidia_api_key="\n",
            openai_compat_api_key=" ",
            openai_compat_text_model="demo",
        )
    )

    assert order == ["ollama"]


def test_provider_order_auto_includes_configured_remote_fallbacks():
    order = _provider_order(Settings(_env_file=None, ai_provider="auto", openrouter_api_key="router", nvidia_api_key="nvidia"))

    assert order == [
        "nvidia",
        "openrouter",
        "ollama",
    ]


def test_provider_order_auto_prefers_router9_when_connected():
    order = _provider_order(Settings(_env_file=None, ai_provider="auto", router9_api_key="secret", openrouter_api_key="router", nvidia_api_key="nvidia"))

    assert order == [
        "router9",
        "nvidia",
        "openrouter",
        "ollama",
    ]





def test_provider_order_prefers_local_gpt_oss_when_selected():
    order = _provider_order(Settings(_env_file=None, openrouter_api_key="secret"), "ollama")

    assert order == ["ollama", "openrouter"]


def test_provider_order_mock_skips_ai_providers():
    assert _provider_order(Settings(_env_file=None), "mock") == []


def test_provider_order_router9_direct_selection_can_fallback_when_not_only_mode():
    order = _provider_order(Settings(_env_file=None, router9_api_key="router9", openrouter_api_key="router", nvidia_api_key="nvidia"), "router9")

    assert order == [
        "router9",
        "openrouter",
        "nvidia",
        "ollama",
    ]


def test_provider_order_router9_only_restricts_to_router9():
    assert _provider_order(Settings(_env_file=None, router9_only=True), "auto") == ["router9"]
    assert _provider_order(Settings(_env_file=None, router9_only=True), "router9") == ["router9"]


def test_provider_order_router9_only_rejects_other_providers():
    try:
        _provider_order(Settings(_env_file=None, router9_only=True), "nvidia")
    except RuntimeError as error:
        assert "9router-only" in str(error)
    else:
        raise AssertionError("Expected router9-only mode to reject non-router9 provider")


def test_empty_runtime_settings_do_not_override_environment_settings():
    settings = Settings(ai_provider="openrouter", ollama_base_url="https://ollama.com/v1", ollama_api_key="secret")
    merged = merge_runtime_settings(settings, RuntimeSettings())

    assert merged.ai_provider == "openrouter"
    assert merged.ollama_base_url == "https://ollama.com/v1"
    assert merged.ollama_api_key == "secret"


def test_partial_runtime_settings_override_only_provided_values():
    settings = Settings(ai_provider="openrouter", ollama_base_url="https://ollama.com/v1", ollama_api_key="secret")
    runtime_settings = RuntimeSettings.model_validate({"default_provider": "ollama", "ollama": {"model": "gpt-oss:20b"}})
    merged = merge_runtime_settings(settings, runtime_settings)

    assert merged.ai_provider == "ollama"
    assert merged.ollama_base_url == "https://ollama.com/v1"
    assert merged.ollama_api_key == "secret"
    assert merged.ollama_text_model == "gpt-oss:20b"


def test_runtime_settings_merge_router9_values():
    settings = Settings(router9_base_url="https://old.example/v1", router9_api_key="old", router9_allowed_models=[])
    runtime_settings = RuntimeSettings.model_validate({
        "router9": {
            "model": "provider/model-a",
            "only_mode": True,
            "allowed_model_ids": ["provider/model-a"],
        }
    })
    merged = merge_runtime_settings(settings, runtime_settings)

    assert merged.router9_api_key == "old"
    assert merged.router9_base_url == "https://old.example/v1"
    assert merged.router9_text_model == "provider/model-a"
    assert merged.router9_only is True
    assert merged.router9_allowed_models == ["provider/model-a"]


def test_router9_default_base_url_targets_local_gateway():
    assert Settings(_env_file=None).router9_base_url == "http://localhost:20128/v1"


def test_runtime_settings_ignore_blank_provider_overrides():
    settings = Settings(
        openrouter_api_key="env-openrouter",
        openrouter_base_url="https://env-openrouter.example/v1",
        openrouter_text_model="env/model",
        openrouter_http_referer="https://env.example",
        openrouter_x_title="Env title",
    )
    runtime_settings = RuntimeSettings.model_validate({
        "openrouter": {"model": "\t"},
        "openrouter_http_referer": " ",
        "openrouter_x_title": "",
    })

    merged = merge_runtime_settings(settings, runtime_settings)

    assert merged.openrouter_api_key == "env-openrouter"
    assert merged.openrouter_base_url == "https://env-openrouter.example/v1"
    assert merged.openrouter_text_model == "env/model"
    assert merged.openrouter_http_referer == "https://env.example"
    assert merged.openrouter_x_title == "Env title"


def test_runtime_settings_router9_only_can_override_false():
    settings = Settings(router9_only=True)
    runtime_settings = RuntimeSettings.model_validate({"router9": {"only_mode": False}})

    merged = merge_runtime_settings(settings, runtime_settings)

    assert merged.router9_only is False


def test_select_codex_model_ids_keeps_5_1_and_newer():
    models = [
        AiModelInfo(id="cc/codex-5", label="cc/codex-5"),
        AiModelInfo(id="cc/codex-5.1", label="cc/codex-5.1"),
        AiModelInfo(id="cc/codex-5.5", label="cc/codex-5.5"),
        AiModelInfo(id="openai/gpt-5.2", label="openai/gpt-5.2"),
        AiModelInfo(id="codex-mini-6", label="codex-mini-6"),
    ]

    selected = select_codex_model_ids(models)

    assert selected == ["codex-mini-6", "cc/codex-5.5", "cc/codex-5.1"]


def test_select_router9_preferred_models_match_requested_order():
    models = [
        AiModelInfo(id="gh/gpt-5.2", label="gh/gpt-5.2"),
        AiModelInfo(id="cc/codex-5.4-image", label="cc/codex-5.4-image"),
        AiModelInfo(id="cc/codex-5.5-image", label="cc/codex-5.5-image"),
        AiModelInfo(id="cc/codex-5.3", label="cc/codex-5.3"),
        AiModelInfo(id="cc/codex-5.4", label="cc/codex-5.4"),
        AiModelInfo(id="cc/codex-5.5", label="cc/codex-5.5"),
    ]

    assert select_router9_ocr_model_ids(models) == ["cc/codex-5.5-image", "cc/codex-5.4-image", "gh/gpt-5.2"]
    assert select_router9_render_model_ids(models) == ["cc/codex-5.5", "cc/codex-5.5-image", "cc/codex-5.4", "cc/codex-5.4-image", "cc/codex-5.3", "gh/gpt-5.2"]


def test_bootstrap_router9_models_adds_codex_defaults(monkeypatch):
    async def fake_list_models(self):
        return [
            AiModelInfo(id="gh/gpt-5.2", label="gh/gpt-5.2"),
            AiModelInfo(id="cc/codex-5.4-image", label="cc/codex-5.4-image"),
            AiModelInfo(id="cc/codex-5.5-image", label="cc/codex-5.5-image"),
            AiModelInfo(id="cc/codex-5.3", label="cc/codex-5.3"),
            AiModelInfo(id="cc/codex-5.4", label="cc/codex-5.4"),
            AiModelInfo(id="cc/codex-5.5", label="cc/codex-5.5"),
        ]

    settings = Settings(router9_api_key="secret", router9_allowed_models=["existing/model"])
    monkeypatch.setattr("app.services.router9_client.Router9Client.list_models", fake_list_models)

    asyncio.run(bootstrap_router9_models(settings))

    assert settings.router9_allowed_models == [
        "existing/model",
        "cc/codex-5.5-image",
        "cc/codex-5.4-image",
        "gh/gpt-5.2",
        "cc/codex-5.5",
        "cc/codex-5.4",
        "cc/codex-5.3",
    ]
    assert settings.router9_text_model == "cc/codex-5.5"
    assert settings.router9_ocr_model == "cc/codex-5.5-image"


def test_model_scan_provider_rejects_unknown_provider_ids():
    from pydantic import ValidationError

    from app.schemas.scene import ProviderModelScanRequest

    for provider in ["not_a_provider", "openai", "vllm"]:
        with pytest.raises(ValidationError):
            ProviderModelScanRequest(provider=provider)



def test_openai_compat_scan_models_uses_models_endpoint_without_api_key(monkeypatch):
    from app.services.model_scan import list_provider_models

    calls = []

    class FakeAsyncClient:
        def __init__(self, timeout: int) -> None:
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url: str, headers: dict[str, str], timeout=None):
            calls.append((url, headers, self.timeout))
            return httpx.Response(200, json={"data": [{"id": "deepseek-chat", "owned_by": "deepseek", "input_modalities": ["text", "image"], "supported_parameters": ["temperature"]}]})

    monkeypatch.setattr("app.services.http_pool.get_client", lambda *args, **kwargs: FakeAsyncClient(kwargs.get("timeout") or args[1] if len(args) > 1 else 20))

    settings = Settings(_env_file=None, openai_compat_base_url="https://deepseek-reverse-api.sin-studio.tech/v1/chat/completions")
    models = asyncio.run(list_provider_models(settings, "openai_compat"))

    assert calls[0][0] == "https://deepseek-reverse-api.sin-studio.tech/v1/models"
    assert calls[0][1] == {}
    assert models[0].id == "deepseek-chat"
    assert models[0].provider == "openai_compat"
    assert models[0].capabilities == {"input_modalities": ["text", "image"], "supported_parameters": ["temperature"]}


def test_openai_compat_scan_models_falls_back_to_v1_models(monkeypatch):
    from app.services.model_scan import list_provider_models

    calls = []

    class FakeAsyncClient:
        async def get(self, url: str, headers: dict[str, str], timeout=None):
            calls.append(url)
            if url == "https://compat.local/models":
                return httpx.Response(404, json={"error": "not found"})
            return httpx.Response(200, json={"data": [{"id": "compat/model"}]})

    monkeypatch.setattr("app.services.http_pool.get_client", lambda *args, **kwargs: FakeAsyncClient())

    settings = Settings(_env_file=None, openai_compat_base_url="https://compat.local")
    models = asyncio.run(list_provider_models(settings, "openai_compat"))

    assert calls == ["https://compat.local/models", "https://compat.local/v1/models"]
    assert models[0].id == "compat/model"


def test_router9_list_models_uses_openai_compatible_models_endpoint(monkeypatch):
    calls = []

    class FakeAsyncClient:
        def __init__(self, timeout: int) -> None:
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url: str, headers: dict[str, str], timeout=None):
            calls.append((url, headers))
            return httpx.Response(
                200,
                json={"data": [{"id": "cc/claude-opus-4-6", "owned_by": "claude-code", "context_length": 200000, "capabilities": {"vision": True}, "modalities": ["text", "image"]}]},
            )

    monkeypatch.setattr("app.services.http_pool.get_client", lambda *args, **kwargs: FakeAsyncClient(kwargs.get("timeout") or args[1] if len(args) > 1 else 20))

    models = asyncio.run(Router9Client(Settings(_env_file=None, router9_api_key="secret")).list_models())

    assert calls[0][0] == "http://localhost:20128/v1/models"
    assert calls[0][1]["Authorization"] == "Bearer secret"
    assert models[0].id == "cc/claude-opus-4-6"
    assert models[0].context_length == 200000
    assert models[0].capabilities == {"capabilities": {"vision": True}, "modalities": ["text", "image"]}


def test_router9_chat_payload_uses_non_streaming_transport(monkeypatch):
    payloads = []

    class FakeAsyncClient:
        def __init__(self, timeout: int) -> None:
            self.timeout = timeout

        async def post(self, url: str, headers: dict[str, str], json: dict, timeout=None):
            payloads.append((url, headers, json))
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": '{"problem_text":"x","renderer":"geogebra_2d","objects":[],"view":{"dimension":"2d"}}'}}]},
            )

    monkeypatch.setattr("app.services.http_pool.get_client", lambda *args, **kwargs: FakeAsyncClient(kwargs.get("timeout") or args[1] if len(args) > 1 else 20))

    scene = asyncio.run(
        Router9Client(Settings(_env_file=None, router9_api_key="secret"), model="cc/claude-opus-4-6").extract_scene_json("x")
    )

    assert payloads[0][0] == "http://localhost:20128/v1/chat/completions"
    assert payloads[0][2]["model"] == "cc/claude-opus-4-6"
    assert payloads[0][2]["stream"] is False
    assert "response_format" not in payloads[0][2]
    assert scene["renderer"] == "geogebra_2d"


def test_extract_chat_message_content_accepts_part_lists():
    from app.services.chat_response import extract_chat_message_content

    assert extract_chat_message_content({"content": [{"type": "text", "text": "hello"}, {"type": "text", "text": " world"}]}) == "hello world"
    assert extract_chat_message_content({"content": [{"type": "output_text", "content": "hello"}]}) == "hello"
    assert extract_chat_message_content({"content": "", "reasoning_content": "hello from reasoning"}) == "hello from reasoning"


def test_extract_chat_response_content_accepts_responses_shapes():
    from app.services.chat_response import extract_chat_response_content

    assert extract_chat_response_content({"output_text": "hello"}) == "hello"
    assert extract_chat_response_content({"output": [{"content": [{"type": "output_text", "text": "hello"}, {"type": "output_text", "text": " world"}]}]}) == "hello world"


def test_render_fallback_success_returns_prior_failures_as_warnings(monkeypatch):
    async def fake_extract(provider, settings, problem_text, grade, reasoning_layer, registry, preferred_ai_model=None):
        if provider == "nvidia":
            raise RuntimeError("quota exceeded")
        return {"problem_text": problem_text, "renderer": "geogebra_2d", "objects": [], "view": {"dimension": "2d"}}

    monkeypatch.setattr("app.services.extractor._extract_with_provider", fake_extract)

    monkeypatch.setattr("app.services.model_registry.get_settings", lambda: Settings(_env_file=None, ai_provider="nvidia", nvidia_api_key="secret"))
    scene, warnings = asyncio.run(extract_scene("x", runtime_settings=RuntimeSettings.model_validate({"default_provider": "nvidia"})))

    assert scene.renderer == "geogebra_2d"
    assert any("AI fallback: nvidia/" in warning and "quota exceeded" in warning for warning in warnings)


def test_render_continues_after_invalid_ai_response(monkeypatch):
    calls = []

    async def fake_extract(provider, settings, problem_text, grade, reasoning_layer, registry, preferred_ai_model=None, **kwargs):
        calls.append((provider, preferred_ai_model))
        return {"problem_text": problem_text, "renderer": "geogebra_2d", "objects": [{"type": "point_2d"}], "view": {"dimension": "2d"}}

    monkeypatch.setattr("app.services.extractor._extract_with_provider", fake_extract)
    monkeypatch.setattr(
        "app.services.model_registry.get_settings",
        lambda: Settings(_env_file=None, ai_provider="router9", router9_api_key="router9-secret", router9_text_model="cx/gpt-5.5", router9_allowed_models=["cx/gpt-5.5"]),
    )

    scene, warnings = asyncio.run(extract_scene(
        "x",
        runtime_settings=RuntimeSettings.model_validate({
            "default_provider": "router9",
            "router9": {"model": "cx/gpt-5.5"},
            "openrouter": {"model": "openrouter/model"},
        }),
    ))

    assert scene.topic == "unknown"
    assert calls[0] == ("router9", "cx/gpt-5.5")
    assert len(calls) >= 1
    assert any("AI đã phản hồi nhưng scene không hợp lệ" in warning for warning in warnings)


def test_render_profile_fallback_models_are_used_only_without_explicit_model(monkeypatch):
    from app.services.model_registry import TaskProfile
    from app.services.extractor import _profile_model_candidates

    profile = TaskProfile("render", "router9", "cx/gpt-5.5", ["gh/gemini-3.1-pro-preview"])
    settings = Settings(_env_file=None, router9_api_key="secret", router9_allowed_models=["cx/gpt-5.5", "gh/gemini-3.1-pro-preview"])

    assert _profile_model_candidates(profile, "router9", settings, None) == ["cx/gpt-5.5", "gh/gemini-3.1-pro-preview"]
    assert _profile_model_candidates(profile, "router9", settings, "cx/gpt-5.5") == ["cx/gpt-5.5"]


def test_render_profile_fallback_models_for_provider_alias_require_no_explicit_model(monkeypatch):
    from app.services.model_registry import TaskProfile
    from app.services.extractor import _profile_model_candidates

    profile = TaskProfile("render", "ollama", "gpt-oss:120b", ["gpt-oss:20b"])
    settings = Settings(_env_file=None, ollama_text_model="gpt-oss:120b")

    assert _profile_model_candidates(profile, "ollama", settings, None) == ["gpt-oss:120b", "gpt-oss:20b"]
    assert _profile_model_candidates(profile, "ollama", settings, "gpt-oss:120b") == ["gpt-oss:120b"]


def test_openrouter_base_url_normalizes_missing_api_segment():
    from app.services.openrouter_client import openrouter_api_base_url

    assert openrouter_api_base_url(Settings(_env_file=None, openrouter_base_url="https://openrouter.ai/v1")) == "https://openrouter.ai/api/v1"


def test_ollama_cloud_scan_uses_openai_models_endpoint(monkeypatch):
    from app.services.model_scan import list_provider_models

    calls = []

    class FakeClient:
        is_closed = False

        async def get(self, url: str, headers: dict[str, str], timeout=None):
            calls.append((url, headers))
            return httpx.Response(200, json={"data": [{"id": "gpt-oss:120b"}]})

    monkeypatch.setattr("app.services.model_scan.get_client", lambda *args, **kwargs: FakeClient(), raising=False)
    monkeypatch.setattr("app.services.http_pool.get_client", lambda *args, **kwargs: FakeClient())

    models = asyncio.run(list_provider_models(Settings(_env_file=None, ollama_base_url="https://ollama.com/v1", ollama_api_key="secret"), "ollama"))

    assert calls[0][0] == "https://ollama.com/v1/models"
    assert models[0].id == "gpt-oss:120b"


def test_render_router9_allowlist_uses_single_selected_model(monkeypatch):
    calls = []

    async def fake_extract(provider, settings, problem_text, grade, reasoning_layer, registry, preferred_ai_model=None):
        calls.append((provider, preferred_ai_model))
        return {"problem_text": problem_text, "renderer": "geogebra_2d", "objects": [], "view": {"dimension": "2d"}}

    monkeypatch.setattr("app.services.extractor._extract_with_provider", fake_extract)
    monkeypatch.setattr(
        "app.services.model_registry.get_settings",
        lambda: Settings(_env_file=None, router9_api_key="secret", router9_allowed_models=["cc/codex-5.5", "cc/codex-5.4", "cc/codex-5.3", "gh/gpt-5.2"]),
    )

    runtime_settings = RuntimeSettings.model_validate({"router9": {}})
    scene, warnings = asyncio.run(extract_scene("x", runtime_settings=runtime_settings))

    assert scene.topic == "unknown"
    assert calls == [("router9", "cc/codex-5.5")]
    assert warnings == []


def test_render_router9_accepts_explicit_vendor_prefixed_model(monkeypatch):
    calls = []

    async def fake_extract(provider, settings, problem_text, grade, reasoning_layer, registry, preferred_ai_model=None, **kwargs):
        calls.append((provider, preferred_ai_model))
        return {"problem_text": problem_text, "renderer": "geogebra_2d", "objects": [], "view": {"dimension": "2d"}}

    monkeypatch.setattr("app.services.extractor._extract_with_provider", fake_extract)

    runtime_settings = RuntimeSettings.model_validate({
        "router9": {
            "model": "cx/gpt-5.5",
            "allowed_model_ids": ["cx/gpt-5.5", "google/gemini-2.5-pro"],
        }
    })
    scene, warnings = asyncio.run(extract_scene(
        "x",
        preferred_ai_provider="router9",
        preferred_ai_model="google/gemini-2.5-pro",
        runtime_settings=runtime_settings,
    ))

    assert scene.topic == "unknown"
    assert calls == [("router9", "google/gemini-2.5-pro")]
    assert warnings == []


def test_render_explicit_model_bypasses_registry_task_profile(monkeypatch):
    from app.services.model_registry import ModelRegistry, ModelRegistryItem, ProviderRegistryItem, TaskProfile

    calls = []

    async def fake_extract(provider, settings, problem_text, grade, reasoning_layer, registry, preferred_ai_model=None, **kwargs):
        calls.append((provider, preferred_ai_model))
        return {"problem_text": problem_text, "renderer": "geogebra_2d", "objects": [], "view": {"dimension": "2d"}}

    registry = ModelRegistry(
        providers={
            "router9": ProviderRegistryItem(
                id="router9",
                label="9router",
                base_url="https://api-9router.sin-studio.tech/v1",
                api_key_configured=True,
            )
        },
        models={
            "router9": [
                ModelRegistryItem("router9", "cx/gpt-5.5", "cx/gpt-5.5", allowed=True),
                ModelRegistryItem("router9", "google/gemini-2.5-pro", "google/gemini-2.5-pro", allowed=True),
            ]
        },
        task_profiles={"render": TaskProfile("render", "router9", "cx/gpt-5.5", [])},
        settings={"default_provider": "router9"},
    )

    async def fake_load_model_registry(_db, _settings=None):
        return registry

    monkeypatch.setattr("app.services.extractor._extract_with_provider", fake_extract)
    monkeypatch.setattr("app.services.extractor.load_model_registry", fake_load_model_registry)
    monkeypatch.setattr("app.services.model_registry.load_model_registry", fake_load_model_registry)

    runtime_settings = RuntimeSettings.model_validate({
        "router9": {
            "model": "cx/gpt-5.5",
            "allowed_model_ids": ["cx/gpt-5.5", "google/gemini-2.5-pro"],
        }
    })
    scene, warnings = asyncio.run(extract_scene(
        "x",
        preferred_ai_provider="router9",
        preferred_ai_model="google/gemini-2.5-pro",
        runtime_settings=runtime_settings,
        db=object(),
    ))

    assert scene.topic == "unknown"
    assert calls == [("router9", "google/gemini-2.5-pro")]
    assert warnings == []


def test_render_provider_selection_uses_runtime_model_when_payload_model_missing(monkeypatch):
    calls = []

    async def fake_extract(provider, settings, problem_text, grade, reasoning_layer, registry, preferred_ai_model=None, **kwargs):
        calls.append((provider, preferred_ai_model))
        return {"problem_text": problem_text, "renderer": "geogebra_2d", "objects": [], "view": {"dimension": "2d"}}

    monkeypatch.setattr("app.services.extractor._extract_with_provider", fake_extract)

    runtime_settings = RuntimeSettings.model_validate({
        "router9": {
            "model": "google/gemini-2.5-pro",
            "allowed_model_ids": ["cx/gpt-5.5", "google/gemini-2.5-pro"],
        }
    })
    scene, warnings = asyncio.run(extract_scene(
        "x",
        preferred_ai_provider="router9",
        preferred_ai_model=None,
        runtime_settings=runtime_settings,
    ))

    assert scene.topic == "unknown"
    assert calls == [("router9", "google/gemini-2.5-pro")]
    assert warnings == []


def test_render_explicit_openai_compat_is_tried_before_fallback_without_api_key(monkeypatch):
    calls = []

    async def fake_extract(provider, settings, problem_text, grade, reasoning_layer, registry, preferred_ai_model=None, **kwargs):
        calls.append((provider, preferred_ai_model))
        return {"problem_text": problem_text, "renderer": "geogebra_2d", "objects": [], "view": {"dimension": "2d"}}

    monkeypatch.setattr("app.services.extractor._extract_with_provider", fake_extract)

    runtime_settings = RuntimeSettings.model_validate({
        "openai_compat": {
            "model": "deepseek-v4-flash",
        },
        "router9": {
            "model": "cx/gpt-5.5",
            "allowed_model_ids": ["cx/gpt-5.5"],
        },
    })
    scene, warnings = asyncio.run(extract_scene(
        "x",
        preferred_ai_provider="openai_compat",
        preferred_ai_model="deepseek-v4-flash",
        runtime_settings=runtime_settings,
    ))

    assert scene.topic == "unknown"
    assert calls == [("openai_compat", "deepseek-v4-flash")]
    assert warnings == []


def test_render_explicit_model_does_not_fallback_to_other_providers(monkeypatch):
    calls = []

    async def fail_extract(provider, settings, problem_text, grade, reasoning_layer, registry, preferred_ai_model=None, **kwargs):
        calls.append((provider, preferred_ai_model))
        raise RuntimeError(f"{provider} unavailable")

    monkeypatch.setattr("app.services.extractor._extract_with_provider", fail_extract)

    runtime_settings = RuntimeSettings.model_validate({
        "openai_compat": {
            "model": "deepseek-v4-flash",
        },
        "router9": {
            "model": "cx/gpt-5.5",
            "allowed_model_ids": ["cx/gpt-5.5"],
        },
        "nvidia": {
            "model": "qwen/qwen3-coder-480b-a35b-instruct",
        },
    })

    with pytest.raises(RuntimeError) as error:
        asyncio.run(extract_scene(
            "x",
            preferred_ai_provider="openai_compat",
            preferred_ai_model="deepseek-v4-flash",
            runtime_settings=runtime_settings,
        ))

    assert calls == [("openai_compat", "deepseek-v4-flash")]
    assert "Không fallback sang provider ngoài lựa chọn" in str(error.value)
    assert "router9/" not in str(error.value)
    assert "nvidia/" not in str(error.value)


def test_render_explicit_model_ignores_configured_profile_fallbacks(monkeypatch):
    from app.services.model_registry import ModelRegistry, ModelRegistryItem, ProviderRegistryItem, TaskProfile

    calls = []

    async def fake_extract(provider, settings, problem_text, grade, reasoning_layer, registry, preferred_ai_model=None, **kwargs):
        calls.append((provider, preferred_ai_model))
        if preferred_ai_model == "deepseek-v4-flash":
            raise RuntimeError("primary failed")
        return {"problem_text": problem_text, "renderer": "geogebra_2d", "objects": [], "view": {"dimension": "2d"}}

    registry = ModelRegistry(
        providers={
            "openai_compat": ProviderRegistryItem(
                id="openai_compat",
                label="OpenAI-compatible",
                base_url="https://deepseek.example/v1",
                api_key_configured=True,
            ),
            "router9": ProviderRegistryItem(
                id="router9",
                label="9router",
                base_url="https://api-9router.sin-studio.tech/v1",
                api_key_configured=True,
            ),
        },
        models={
            "openai_compat": [
                ModelRegistryItem("openai_compat", "deepseek-v4-flash", "deepseek-v4-flash", allowed=True),
                ModelRegistryItem("openai_compat", "deepseek-v4-fallback", "deepseek-v4-fallback", allowed=True),
            ],
            "router9": [
                ModelRegistryItem("router9", "cx/gpt-5.5", "cx/gpt-5.5", allowed=True),
            ],
        },
        task_profiles={
            "render": TaskProfile("render", "openai_compat", "deepseek-v4-flash", ["deepseek-v4-fallback"]),
        },
        settings={"default_provider": "router9"},
    )

    async def fake_load_model_registry(_db, _settings=None):
        return registry

    monkeypatch.setattr("app.services.extractor._extract_with_provider", fake_extract)
    monkeypatch.setattr("app.services.extractor.load_model_registry", fake_load_model_registry)
    monkeypatch.setattr("app.services.model_registry.load_model_registry", fake_load_model_registry)

    runtime_settings = RuntimeSettings.model_validate({
        "openai_compat": {
            "model": "deepseek-v4-flash",
        },
        "router9": {
            "model": "cx/gpt-5.5",
            "allowed_model_ids": ["cx/gpt-5.5"],
        },
    })

    with pytest.raises(RuntimeError) as error:
        asyncio.run(extract_scene(
            "x",
            preferred_ai_provider="openai_compat",
            preferred_ai_model="deepseek-v4-flash",
            runtime_settings=runtime_settings,
            db=object(),
        ))

    assert calls == [("openai_compat", "deepseek-v4-flash")]
    assert "Không fallback sang provider ngoài lựa chọn" in str(error.value)


def test_render_explicit_ollama_alias_uses_ollama_provider(monkeypatch):
    calls = []

    async def fake_extract(provider, settings, problem_text, grade, reasoning_layer, registry, preferred_ai_model=None, **kwargs):
        calls.append((provider, preferred_ai_model))
        return {"problem_text": problem_text, "renderer": "geogebra_2d", "objects": [], "view": {"dimension": "2d"}}

    monkeypatch.setattr("app.services.extractor._extract_with_provider", fake_extract)

    runtime_settings = RuntimeSettings.model_validate({
        "ollama": {
            "model": "gpt-oss:120b",
        },
        "router9": {
            "model": "cx/gpt-5.5",
        },
    })
    scene, warnings = asyncio.run(extract_scene(
        "x",
        preferred_ai_provider="ollama",
        preferred_ai_model="gpt-oss:120b",
        runtime_settings=runtime_settings,
    ))

    assert scene.topic == "unknown"
    assert calls == [("ollama", "gpt-oss:120b")]
    assert warnings == []


def test_render_tries_full_provider_order_before_mock(monkeypatch):
    calls = []

    async def fail_extract(provider, settings, problem_text, grade, reasoning_layer, registry, preferred_ai_model=None, **kwargs):
        calls.append((provider, preferred_ai_model))
        raise RuntimeError(f"{provider} unavailable")

    monkeypatch.setattr("app.services.extractor._extract_with_provider", fail_extract)
    monkeypatch.setattr(
        "app.services.model_registry.get_settings",
        lambda: Settings(
            _env_file=None,
            ai_provider="openrouter",
            openrouter_api_key="router",
            nvidia_api_key="nvidia",
        ),
    )

    runtime_settings = RuntimeSettings.model_validate({
        "default_provider": "openrouter",
        "openrouter": {},
        "nvidia": {},
    })
    # preferred_ai_provider forces the multi-provider legacy fallback path (not tier-only).
    scene, warnings = asyncio.run(extract_scene(
        "x",
        preferred_ai_provider="openrouter",
        runtime_settings=runtime_settings,
    ))

    assert scene.topic == "unknown"
    assert {provider for provider, _ in calls} >= {"openrouter", "nvidia", "ollama"}
    assert warnings[-1] == "Tất cả AI provider đều lỗi; đang dùng mock extractor."


def test_render_skips_openrouter_family_without_api_key(monkeypatch):
    calls = []

    async def fail_extract(provider, settings, problem_text, grade, reasoning_layer, registry, preferred_ai_model=None, **kwargs):
        calls.append((provider, preferred_ai_model))
        raise RuntimeError(f"{provider} unavailable")

    monkeypatch.setattr("app.services.extractor._extract_with_provider", fail_extract)

    monkeypatch.setattr("app.services.model_registry.get_settings", lambda: Settings(_env_file=None, ai_provider="openrouter"))

    scene, warnings = asyncio.run(extract_scene("x"))

    assert scene.topic == "unknown"
    assert [provider for provider, _ in calls] == ["ollama"]
    assert warnings[-1] == "Tất cả AI provider đều lỗi; đang dùng mock extractor."


def test_render_all_ai_failures_warn_with_attempt_chain_before_mock(monkeypatch):
    async def fail_extract(provider, settings, problem_text, grade, reasoning_layer, registry, preferred_ai_model=None, **kwargs):
        raise RuntimeError(f"{provider} unavailable")

    monkeypatch.setattr("app.services.extractor._extract_with_provider", fail_extract)

    monkeypatch.setattr("app.services.model_registry.get_settings", lambda: Settings(_env_file=None, ai_provider="openrouter", openrouter_api_key="router"))
    scene, warnings = asyncio.run(extract_scene("x", runtime_settings=RuntimeSettings.model_validate({"default_provider": "openrouter"})))

    assert scene.topic == "unknown"
    assert any("AI fallback: openrouter/" in warning for warning in warnings)
    assert warnings[-1] == "Tất cả AI provider đều lỗi; đang dùng mock extractor."


def test_render_router9_only_failure_includes_attempted_model(monkeypatch):
    async def fail_extract(provider, settings, problem_text, grade, reasoning_layer, registry, preferred_ai_model=None, **kwargs):
        raise RuntimeError("gateway down")

    monkeypatch.setattr("app.services.extractor._extract_with_provider", fail_extract)
    monkeypatch.setattr(
        "app.services.model_registry.get_settings",
        lambda: Settings(_env_file=None, router9_api_key="secret", router9_allowed_models=["cc/codex-5.5"]),
    )

    try:
        asyncio.run(extract_scene(
            "x",
            preferred_ai_model="cc/codex-5.5",
            runtime_settings=RuntimeSettings.model_validate({"router9": {"only_mode": True}}),
        ))
    except RuntimeError as error:
        message = str(error)
        assert "9router-only" in message
        assert "router9/cc/codex-5.5" in message
        assert "gateway down" in message
    else:
        raise AssertionError("Expected router9-only render failure")


def test_render_route_returns_failure_directly(monkeypatch, tmp_path):
    db = SQLiteClient(str(tmp_path / "render-route.db"))
    asyncio.run(apply_sqlite_migrations(db))
    settings = Settings(_env_file=None, sqlite_path=db.path)
    user = UserRecord("u1", "u@example.com", "hash", "now", "now")
    asyncio.run(db.execute("INSERT INTO users (id, email, password_hash) VALUES (?, ?, ?)", [user.id, user.email, user.password_hash]))

    async def override_db():
        return db

    async def override_user():
        return user

    async def noop(*args, **kwargs):
        return None

    async def fail_response(*args, **kwargs):
        raise RuntimeError("9router-only đang bật nên không fallback sang provider khác.")

    app.dependency_overrides[get_database] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[require_active_user] = override_user
    monkeypatch.setattr("app.api.routes_render.enforce_rate_limit", noop)
    monkeypatch.setattr("app.api.routes_render.enforce_render_access", noop)
    monkeypatch.setattr("app.api.routes_render.build_problem_render_response", fail_response)
    try:
        client = TestClient(app)
        response = client.post("/api/render", json={"problem_text": "x"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"]["debug_message"] == "9router-only đang bật nên không fallback sang provider khác."


def test_solver_explainer_falls_back_when_openrouter_model_is_invalid(monkeypatch):
    calls = []

    class FakeAsyncClient:
        def __init__(self, timeout: int) -> None:
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url: str, headers: dict[str, str], json: dict, timeout=None):
            calls.append(json["model"])
            if json["model"] == "nvidia/nemotron-3-super-120b-a12b:free":
                return httpx.Response(400, json={"error": {"message": "not a valid model ID"}})
            return httpx.Response(200, json={"choices": [{"message": {"content": '{"steps":[{"index":1,"title":"AI","explanation":"LLM fallback worked"}]}'}}]})

    monkeypatch.setattr("app.services.http_pool.get_client", lambda *args, **kwargs: FakeAsyncClient(kwargs.get("timeout") or args[1] if len(args) > 1 else 20))

    data = asyncio.run(_call_explainer(
        {"question": "q", "answer": "a", "warnings": [], "scene_objects": [], "steps": [{"index": 1}]},
        Settings(_env_file=None, openrouter_api_key="secret", openrouter_text_model="openrouter/nvidia/nemotron-3-super-120b-a12b:free"),
    ))

    assert calls == ["nvidia/nemotron-3-super-120b-a12b:free", "openai/gpt-oss-120b:free"]
    assert data["steps"][0]["explanation"] == "LLM fallback worked"


def test_render_scene_route_rebuilds_payload_from_edited_scene(monkeypatch):
    async def no_user():
        return None

    async def noop(*args, **kwargs):
        return None

    app.dependency_overrides[require_active_user] = no_user
    monkeypatch.setattr("app.api.routes_render.enforce_rate_limit", noop)
    monkeypatch.setattr("app.api.routes_render.enforce_render_access", noop)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/render/scene",
                json={
                    "scene": {
                        "problem_text": "edited",
                        "grade": 10,
                        "topic": "coordinate_2d",
                        "renderer": "geogebra_2d",
                        "objects": [
                            {"type": "point_2d", "name": "A", "x": 0, "y": 0},
                            {"type": "point_2d", "name": "B", "x": 1, "y": 1},
                            {"type": "line_2d", "name": "d1", "through": ["A", "B"]},
                        ],
                        "relations": [],
                        "annotations": [],
                        "view": {"dimension": "2d", "show_axes": True, "show_grid": True, "show_coordinates": False},
                    }
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "d1 = Line(A, B)" in response.json()["payload"]["geogebra_commands"]
