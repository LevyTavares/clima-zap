import asyncio

import httpx

from app.core.config import settings
from app.services.whatsapp_session import check_whatsapp_status


def test_check_whatsapp_status_returns_connection_state(monkeypatch):
    settings.evolution_api_url = "https://whatsapp.example"
    settings.evolution_instance_name = "clima-zap"
    settings.evolution_api_key = "test-key"

    async def mock_get(*args, **kwargs):
        url = args[1]
        assert kwargs["headers"]["apikey"] == "test-key"
        assert url == (
            "https://whatsapp.example/instance/connectionState/clima-zap"
        )
        return httpx.Response(
            200,
            json={"instance": "clima-zap", "state": "open"},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    assert asyncio.run(check_whatsapp_status()) == {
        "instance": "clima-zap",
        "state": "open",
    }


def test_check_whatsapp_status_returns_disconnected_on_http_error(monkeypatch):
    async def mock_get(*args, **kwargs):
        assert "apikey" in kwargs["headers"]
        request = httpx.Request("GET", args[1])
        raise httpx.ConnectError("connection failed", request=request)

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    assert asyncio.run(check_whatsapp_status()) == {"state": "DISCONNECTED"}
