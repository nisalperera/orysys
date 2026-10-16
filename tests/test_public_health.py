import asyncio
import json
import pytest
from app.api.health import public_healthcheck


@pytest.mark.asyncio
async def test_health_filters_success_details():
    async def check():
        return {"ok": True, "base_url": "private-host", "model": "private-model"}
    assert await public_healthcheck(check) == {"status": "ok", "llm": {"ok": True}}


@pytest.mark.asyncio
async def test_health_filters_failure_details():
    async def check():
        return {"ok": False, "error": "private-marker", "base_url": "private-host"}
    result = await public_healthcheck(check)
    assert result["status"] == "degraded"
    assert "private" not in json.dumps(result)


@pytest.mark.asyncio
async def test_health_sanitizes_exception():
    async def check():
        raise RuntimeError("private-marker")
    result = await public_healthcheck(check)
    assert result["llm"]["code"] == "provider_unavailable"
    assert "private-marker" not in json.dumps(result)


@pytest.mark.asyncio
async def test_health_does_not_swallow_cancellation():
    async def check():
        raise asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await public_healthcheck(check)


def test_public_health_route_filters_provider_details(monkeypatch):
    from fastapi.testclient import TestClient
    from app.api.main import create_app
    import app.llm

    async def build_service():
        return object()

    async def check():
        return {"ok": False, "error": "private-marker", "base_url": "private-host"}

    monkeypatch.setattr(app.llm, "llm_healthcheck", check)
    with TestClient(create_app(service_builder=build_service)) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert "private" not in response.text
