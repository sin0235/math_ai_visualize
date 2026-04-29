from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app


def test_settings_defaults_route_hides_api_keys(monkeypatch):
    settings = Settings(
        _env_file=None,
        openrouter_api_key="openrouter-secret",
        nvidia_api_key="nvidia-secret",
        ollama_api_key="ollama-secret",
        router9_api_key="router9-secret",
        router9_text_model="router/model",
        router9_allowed_models=["router/model"],
    )
    monkeypatch.setattr("app.api.routes_settings.get_settings", lambda: settings)

    response = TestClient(app).get("/api/settings/defaults")

    assert response.status_code == 200
    payload = response.json()
    assert "openrouter-secret" not in response.text
    assert "nvidia-secret" not in response.text
    assert "ollama-secret" not in response.text
    assert "router9-secret" not in response.text
    assert payload["openrouter"]["api_key_configured"] is True
    assert payload["nvidia"]["api_key_configured"] is True
    assert payload["ollama"]["api_key_configured"] is True
    assert payload["router9"]["api_key_configured"] is True
    assert payload["router9"]["model"] == "router/model"
    assert payload["router9"]["allowed_model_ids"] == ["router/model"]
