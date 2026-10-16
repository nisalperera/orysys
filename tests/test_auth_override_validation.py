import json
import pytest
from app.auth.dependencies import authenticate_token, validate_token_config


def test_absent_override_allows_documented_demo_key(monkeypatch):
    monkeypatch.delenv("API_TOKENS", raising=False)
    validate_token_config()
    assert authenticate_token("dev-viewer-key").user_id == "viewer1"


def test_valid_override_replaces_demo_keys(monkeypatch):
    monkeypatch.setenv("API_TOKENS", json.dumps({"custom-test-key": "analyst1"}))
    validate_token_config()
    assert authenticate_token("custom-test-key").user_id == "analyst1"
    assert authenticate_token("dev-viewer-key") is None


@pytest.mark.parametrize("value", [
    "", "{invalid-json}", "[]", "null", '"text"',
    '{"key":"unknown-user"}', '{"key":1}', '{"key":null}',
    '{"":"viewer1"}', '{"   ":"viewer1"}',
])
def test_explicit_invalid_override_fails_closed(monkeypatch, value):
    monkeypatch.setenv("API_TOKENS", value)
    with pytest.raises(ValueError, match="API_TOKENS must be"):
        validate_token_config()
    assert authenticate_token("dev-viewer-key") is None
    assert authenticate_token("dev-analyst-key") is None


def test_explicit_empty_mapping_disables_all_keys(monkeypatch):
    monkeypatch.setenv("API_TOKENS", "{}")
    validate_token_config()
    assert authenticate_token("dev-viewer-key") is None
    assert authenticate_token("any-key") is None


def test_startup_rejects_invalid_auth_config(monkeypatch):
    from fastapi.testclient import TestClient
    from app.api.main import create_app
    built = []
    async def build_service():
        built.append(True)
        return object()
    monkeypatch.setenv("API_TOKENS", "invalid-json")
    with pytest.raises(ValueError, match="API_TOKENS must be"):
        with TestClient(create_app(service_builder=build_service)):
            pass
    assert built == []
