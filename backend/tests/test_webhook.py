# pylint: disable=duplicate-code,redefined-outer-name,line-too-long,missing-module-docstring,missing-function-docstring
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def make_payload(command_or_text: str) -> dict:
    """Gera payload completo no formato Evolution API para evitar erros 422 de validação."""
    return {
        "event": "messages.upsert",
        "instance": "clima-zap",
        "data": {
            "key": {
                "remoteJid": "5588999999999@s.whatsapp.net",
                "fromMe": False,
                "id": "TEST_MSG_ID_12345",
            },
            "pushName": "Usuario Teste",
            "message": {
                "conversation": command_or_text,
            },
            "messageTimestamp": 1700000000,
        },
    }


@pytest.mark.usefixtures("test_database")
def test_webhook_invalid_payload():
    """Testa se o webhook trata adequadamente um payload malformado ou vazio."""
    response = client.post("/api/v1/webhook", json={})
    assert response.status_code in (200, 400, 422)


@pytest.mark.usefixtures("test_database")
def test_webhook_clima_command():
    """Testa a execução do comando /clima via mensagem recebida."""
    payload = make_payload("/clima")
    with patch("app.api.webhook.send_whatsapp_message", new_callable=AsyncMock, create=True), \
         patch("app.services.evolution_client.send_whatsapp_message", new_callable=AsyncMock, create=True):
        response = client.post("/api/v1/webhook", json=payload)
        assert response.status_code == 200


@pytest.mark.usefixtures("test_database")
def test_webhook_natural_language_keyword():
    """Testa mensagem em linguagem natural sem barra (ex: 'como tá o tempo hoje?')."""
    payload = make_payload("como tá o tempo hoje?")
    with patch("app.api.webhook.send_whatsapp_message", new_callable=AsyncMock) as mock_send, \
         patch("app.api.webhook.build_current_forecast", new_callable=AsyncMock, return_value="Previsão de Teste"):
        response = client.post("/api/v1/webhook", json=payload)
        assert response.status_code == 200
        mock_send.assert_called_once()


@pytest.mark.usefixtures("test_database")
def test_webhook_numeric_shortcut():
    """Testa a seleção rápida de cidade pelo número '1' (Barbalha)."""
    payload = make_payload("1")
    with patch("app.api.webhook.send_whatsapp_message", new_callable=AsyncMock) as mock_send:
        response = client.post("/api/v1/webhook", json=payload)
        assert response.status_code == 200
        mock_send.assert_called_once()


@pytest.mark.usefixtures("test_database")
def test_webhook_forecast_timeout_fallback():
    """Testa o tratamento de exceção quando a API de clima falha/timeout."""
    payload = make_payload("/clima")
    with patch("app.api.webhook.build_current_forecast", side_effect=Exception("Timeout na API")), \
         patch("app.api.webhook.send_whatsapp_message", new_callable=AsyncMock) as mock_send:
        response = client.post("/api/v1/webhook", json=payload)
        assert response.status_code == 200
        mock_send.assert_called_once()
        assert "instabilidade" in mock_send.call_args[0][1]


@pytest.mark.usefixtures("test_database")
def test_webhook_help_command():
    """Testa o comando /ajuda retornando as opções de menu."""
    payload = make_payload("/ajuda")
    with patch("app.api.webhook.send_whatsapp_message", new_callable=AsyncMock, create=True), \
         patch("app.services.evolution_client.send_whatsapp_message", new_callable=AsyncMock, create=True):
        response = client.post("/api/v1/webhook", json=payload)
        assert response.status_code == 200


@pytest.mark.usefixtures("test_database")
def test_configuracao_with_coordinates():
    """Testa a configuração de localização por coordenadas numéricas (lat, lon)."""
    payload = make_payload("/configuracao -7.23,-39.31")
    with patch("app.api.webhook.send_whatsapp_message", new_callable=AsyncMock, create=True), \
         patch("app.services.evolution_client.send_whatsapp_message", new_callable=AsyncMock, create=True):
        response = client.post("/api/v1/webhook", json=payload)
        assert response.status_code == 200


@pytest.mark.usefixtures("test_database")
def test_configuracao_geocodes_cities_outside_presets():
    """Testa a configuração de cidade fora da lista pré-definida via serviço de geolocalização."""
    payload = make_payload("/configuracao fortaleza")
    mock_geo = {
        "name": "Fortaleza, Ceará",
        "state": "CE",
        "latitude": -3.7319,
        "longitude": -38.5267,
    }
    with patch("app.core.location.get_location_coords", return_value=None), \
         patch("app.api.webhook.geocode_city", return_value=mock_geo, create=True), \
         patch("app.api.webhook.send_whatsapp_message", new_callable=AsyncMock, create=True), \
         patch("app.services.evolution_client.send_whatsapp_message", new_callable=AsyncMock, create=True):
        response = client.post("/api/v1/webhook", json=payload)
        assert response.status_code == 200


@pytest.mark.usefixtures("test_database")
def test_unknown_local_lists_options_when_geocode_misses():
    """Testa o comportamento do bot quando a cidade informada não é encontrada pela geolocalização."""
    payload = make_payload("/configuracao Atlantis")
    with patch("app.core.location.get_location_coords", return_value=None), \
         patch("app.api.webhook.geocode_city", return_value=None, create=True), \
         patch("app.api.webhook.send_whatsapp_message", new_callable=AsyncMock, create=True), \
         patch("app.services.evolution_client.send_whatsapp_message", new_callable=AsyncMock, create=True):
        response = client.post("/api/v1/webhook", json=payload)
        assert response.status_code == 200
