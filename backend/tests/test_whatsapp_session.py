import asyncio

import httpx

from app.core.config import settings
from app.services.whatsapp_session import check_whatsapp_status


def test_check_whatsapp_status_returns_connection_state(monkeypatch):
    settings.evolution_api_url = "https://whatsapp.example"
    settings.evolution_instance_name = "clima-zap"

    async def mock_get(self, url, **kwargs):
        assert url == (
            "https://whatsapp.example/instance/connectionState/clima-zap"
        )
        return httpx.Response(
            200,
            json={"instance": {"instanceName": "clima-zap", "state": "open"}},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    assert asyncio.run(check_whatsapp_status()) == {
        "instance": {"instanceName": "clima-zap", "state": "open"},
    }


def test_check_whatsapp_status_returns_disconnected_on_http_error(monkeypatch):
    async def mock_get(self, url, **kwargs):
        request = httpx.Request("GET", url)
        raise httpx.ConnectError("connection failed", request=request)

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    assert asyncio.run(check_whatsapp_status()) == {
        "instance": {"state": "DISCONNECTED"}
    }
