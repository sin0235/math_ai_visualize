import asyncio

import httpx
from fastapi.testclient import TestClient

from app.core.config import Settings, merge_runtime_settings
from app.main import app
from app.schemas.scene import AiModelInfo, OcrRequest, RenderRequest, RuntimeSettings
from app.services.extractor import extract_scene, _provider_order
from app.services.provider_logging import format_provider_error, redact_sensitive
from app.services.router9_bootstrap import bootstrap_router9_models, select_codex_model_ids
from app.services.router9_client import Router9Client


def test_render_request_accepts_new_ai_providers():
    base = {"problem_text": "test", "preferred_ai_provider": "opencode_nemotron"}
    assert RenderRequest.model_validate(base).preferred_ai_provider == "opencode_nemotron"

    base["preferred_ai_provider"] = "ollama_gpt_oss"
    assert RenderRequest.model_validate(base).preferred_ai_provider == "ollama_gpt_oss"

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


def test_provider_order_auto_includes_special_fallbacks():
    order = _provider_order(Settings(ai_provider="auto"))

    assert order == [
        "nvidia",
        "openrouter",
        "opencode_nemotron",
        "ollama_gpt_oss",
        "openrouter_gpt_oss",
    ]


def test_provider_order_keeps_nemotron_fallbacks_together():
    order = _provider_order(Settings(), "opencode_nemotron")

    assert order[:4] == ["opencode_nemotron", "openrouter", "ollama_gpt_oss", "openrouter_gpt_oss"]


def test_provider_order_prefers_local_gpt_oss_when_selected():
    order = _provider_order(Settings(), "ollama_gpt_oss")

    assert order[:4] == ["ollama_gpt_oss", "openrouter_gpt_oss", "openrouter", "opencode_nemotron"]


def test_provider_order_mock_skips_ai_providers():
    assert _provider_order(Settings(), "mock") == []


def test_provider_order_router9_direct_selection_can_fallback_when_not_only_mode():
    order = _provider_order(Settings(), "router9")

    assert order == [
        "router9",
        "openrouter",
        "opencode_nemotron",
        "ollama_gpt_oss",
        "openrouter_gpt_oss",
        "nvidia",
    ]


def test_provider_order_router9_only_restricts_to_router9():
    assert _provider_order(Settings(router9_only=True), "auto") == ["router9"]
    assert _provider_order(Settings(router9_only=True), "router9") == ["router9"]


def test_provider_order_router9_only_rejects_other_providers():
    try:
        _provider_order(Settings(router9_only=True), "nvidia")
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
    runtime_settings = RuntimeSettings.model_validate({"default_provider": "ollama_gpt_oss", "ollama": {"model": "gpt-oss:20b"}})
    merged = merge_runtime_settings(settings, runtime_settings)

    assert merged.ai_provider == "ollama_gpt_oss"
    assert merged.ollama_base_url == "https://ollama.com/v1"
    assert merged.ollama_api_key == "secret"
    assert merged.ollama_text_model == "gpt-oss:20b"


def test_runtime_settings_merge_router9_values():
    settings = Settings(router9_base_url="https://old.example/v1", router9_api_key="old", router9_allowed_models=[])
    runtime_settings = RuntimeSettings.model_validate({
        "router9": {
            "api_key": "new",
            "base_url": "https://new.example/v1",
            "model": "provider/model-a",
            "only_mode": True,
            "allowed_model_ids": ["provider/model-a"],
        }
    })
    merged = merge_runtime_settings(settings, runtime_settings)

    assert merged.router9_api_key == "new"
    assert merged.router9_base_url == "https://new.example/v1"
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
        "openrouter": {"api_key": "   ", "base_url": "", "model": "\t"},
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


def test_bootstrap_router9_models_adds_codex_defaults(monkeypatch):
    async def fake_list_models(self):
        return [
            AiModelInfo(id="cc/codex-5.1", label="cc/codex-5.1"),
            AiModelInfo(id="cc/codex-5.5", label="cc/codex-5.5"),
            AiModelInfo(id="cc/codex-5", label="cc/codex-5"),
        ]

    settings = Settings(router9_api_key="secret", router9_allowed_models=["existing/model"])
    monkeypatch.setattr("app.services.router9_client.Router9Client.list_models", fake_list_models)

    asyncio.run(bootstrap_router9_models(settings))

    assert settings.router9_allowed_models == ["existing/model", "cc/codex-5.5", "cc/codex-5.1"]
    assert settings.router9_text_model == "cc/codex-5.5"
    assert settings.router9_ocr_model == "cc/codex-5.5"


def test_router9_list_models_uses_openai_compatible_models_endpoint(monkeypatch):
    calls = []

    class FakeAsyncClient:
        def __init__(self, timeout: int) -> None:
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url: str, headers: dict[str, str]):
            calls.append((url, headers))
            return httpx.Response(
                200,
                json={"data": [{"id": "cc/claude-opus-4-6", "owned_by": "claude-code", "context_length": 200000}]},
            )

    monkeypatch.setattr("app.services.router9_client.httpx.AsyncClient", FakeAsyncClient)

    models = asyncio.run(Router9Client(Settings(_env_file=None, router9_api_key="secret")).list_models())

    assert calls[0][0] == "http://localhost:20128/v1/models"
    assert calls[0][1]["Authorization"] == "Bearer secret"
    assert models[0].id == "cc/claude-opus-4-6"
    assert models[0].context_length == 200000


def test_router9_chat_payload_avoids_response_format(monkeypatch):
    payloads = []

    class FakeAsyncClient:
        def __init__(self, timeout: int) -> None:
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url: str, headers: dict[str, str], json: dict):
            payloads.append((url, headers, json))
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": '{"problem_text":"x","renderer":"geogebra_2d","objects":[],"view":{"dimension":"2d"}}'
                            }
                        }
                    ]
                },
            )

    monkeypatch.setattr("app.services.router9_client.httpx.AsyncClient", FakeAsyncClient)

    scene = asyncio.run(
        Router9Client(Settings(_env_file=None, router9_api_key="secret"), model="cc/claude-opus-4-6").extract_scene_json("x")
    )

    assert payloads[0][0] == "http://localhost:20128/v1/chat/completions"
    assert payloads[0][2]["model"] == "cc/claude-opus-4-6"
    assert payloads[0][2]["stream"] is False
    assert "response_format" not in payloads[0][2]
    assert scene["renderer"] == "geogebra_2d"


def test_render_fallback_success_returns_prior_failures_as_warnings(monkeypatch):
    async def fake_extract(provider, settings, problem_text, grade, reasoning_layer, preferred_ai_model=None):
        if provider == "nvidia":
            raise RuntimeError("quota exceeded")
        return {"problem_text": problem_text, "renderer": "geogebra_2d", "objects": [], "view": {"dimension": "2d"}}

    monkeypatch.setattr("app.services.extractor._extract_with_provider", fake_extract)

    scene, warnings = asyncio.run(extract_scene("x", runtime_settings=RuntimeSettings.model_validate({"default_provider": "nvidia"})))

    assert scene.renderer == "geogebra_2d"
    assert any("AI fallback: nvidia/" in warning and "quota exceeded" in warning for warning in warnings)


def test_render_all_ai_failures_warn_with_attempt_chain_before_mock(monkeypatch):
    async def fail_extract(provider, settings, problem_text, grade, reasoning_layer, preferred_ai_model=None):
        raise RuntimeError(f"{provider} unavailable")

    monkeypatch.setattr("app.services.extractor._extract_with_provider", fail_extract)

    scene, warnings = asyncio.run(extract_scene("x", runtime_settings=RuntimeSettings.model_validate({"default_provider": "openrouter"})))

    assert scene.topic == "unknown"
    assert any("AI fallback: openrouter/" in warning for warning in warnings)
    assert warnings[-1] == "Tất cả AI provider đều lỗi; đang dùng mock extractor."


def test_render_router9_only_failure_includes_attempted_model(monkeypatch):
    async def fail_extract(provider, settings, problem_text, grade, reasoning_layer, preferred_ai_model=None):
        raise RuntimeError("gateway down")

    monkeypatch.setattr("app.services.extractor._extract_with_provider", fail_extract)

    try:
        asyncio.run(extract_scene(
            "x",
            preferred_ai_model="cc/codex-5.5",
            runtime_settings=RuntimeSettings.model_validate({"router9": {"only_mode": True, "api_key": "secret"}}),
        ))
    except RuntimeError as error:
        message = str(error)
        assert "9router-only" in message
        assert "router9/cc/codex-5.5" in message
        assert "gateway down" in message
    else:
        raise AssertionError("Expected router9-only render failure")


def test_render_route_returns_detail_for_ai_runtime_errors(monkeypatch):
    async def fail_extract_scene(*args, **kwargs):
        raise RuntimeError("9router-only đang bật nên không fallback sang provider khác.")

    monkeypatch.setattr("app.api.routes_render.extract_scene", fail_extract_scene)

    response = TestClient(app).post("/api/render", json={"problem_text": "x"})

    assert response.status_code == 400
    assert response.json()["detail"] == "9router-only đang bật nên không fallback sang provider khác."


def test_render_scene_route_rebuilds_payload_from_edited_scene():
    response = TestClient(app).post(
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

    assert response.status_code == 200
    assert "d1 = Line(A, B)" in response.json()["payload"]["geogebra_commands"]
