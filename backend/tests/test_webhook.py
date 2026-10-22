# pylint: disable=duplicate-code,redefined-outer-name,line-too-long,missing-module-docstring,missing-function-docstring
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def make_payload(command_or_text: str) -> dict:
    return {
        "event": "messages.upsert",
        "instance": "clima-zap",
        "data": {
            "key": {
                "remoteJid": "5588999999999@s.whatsapp.net",
                "fromMe": False,
                "id": "TEST_MSG_123",
            },
            "pushName": "Usuario Teste",
            "message": {"conversation": command_or_text},
            "messageTimestamp": 1700000000,
        },
    }


def test_webhook_invalid_payload(test_database):
    response = client.post("/api/v1/webhook", json={})
    assert response.status_code in (200, 400, 422)


def test_webhook_natural_language_keyword(test_database):
    """Testa mensagem em linguagem natural sem barra (ex: 'como tá o tempo hoje?')."""
    payload = make_payload("como tá o tempo hoje?")
    with patch("app.api.webhook.send_whatsapp_message", new_callable=AsyncMock) as mock_send, \
         patch("app.api.webhook.build_current_forecast", new_callable=AsyncMock, return_value="Previsão de Teste"):
        response = client.post("/api/v1/webhook", json=payload)
        assert response.status_code == 200
        mock_send.assert_called_once()


def test_webhook_numeric_shortcut(test_database):
    """Testa a seleção rápida de cidade pelo número '1' (Barbalha)."""
    payload = make_payload("1")
    with patch("app.api.webhook.send_whatsapp_message", new_callable=AsyncMock) as mock_send:
        response = client.post("/api/v1/webhook", json=payload)
        assert response.status_code == 200
        mock_send.assert_called_once()


def test_webhook_forecast_timeout_fallback(test_database):
    """Testa o tratamento de exceção quando a API de clima falha/timeout."""
    payload = make_payload("/clima")
    with patch("app.api.webhook.build_current_forecast", side_effect=Exception("Timeout na API")), \
         patch("app.api.webhook.send_whatsapp_message", new_callable=AsyncMock) as mock_send:
        response = client.post("/api/v1/webhook", json=payload)
        assert response.status_code == 200
        mock_send.assert_called_once()
        assert "instabilidade" in mock_send.call_args[0][1]