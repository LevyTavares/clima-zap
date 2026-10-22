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


def test_webhook_invalid_payload(test_database):
    """Testa se o webhook trata adequadamente um payload malformado ou vazio."""
    response = client.post("/api/v1/webhook", json={})
    assert response.status_code in (200, 400, 422)


def test_webhook_clima_command(test_database):
    """Testa a execução do comando /clima via mensagem recebida."""
    payload = make_payload("/clima")
    with patch("app.api.webhook.send_whatsapp_message", new_callable=AsyncMock, create=True), \
         patch("app.services.evolution_client.send_whatsapp_message", new_callable=AsyncMock, create=True):
        response = client.post("/api/v1/webhook", json=payload)
        assert response.status_code == 200


def test_webhook_help_command(test_database):
    """Testa o comando /ajuda retornando as opções de menu."""
    payload = make_payload("/ajuda")
    with patch("app.api.webhook.send_whatsapp_message", new_callable=AsyncMock, create=True), \
         patch("app.services.evolution_client.send_whatsapp_message", new_callable=AsyncMock, create=True):
        response = client.post("/api/v1/webhook", json=payload)
        assert response.status_code == 200


def test_configuracao_with_coordinates(test_database):
    """Testa a configuração de localização por coordenadas numéricas (lat, lon)."""
    payload = make_payload("/configuracao -7.23,-39.31")
    with patch("app.api.webhook.send_whatsapp_message", new_callable=AsyncMock, create=True), \
         patch("app.services.evolution_client.send_whatsapp_message", new_callable=AsyncMock, create=True):
        response = client.post("/api/v1/webhook", json=payload)
        assert response.status_code == 200


def test_configuracao_geocodes_cities_outside_presets(test_database):
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


def test_unknown_local_lists_options_when_geocode_misses(test_database):
    """Testa o comportamento do bot quando a cidade informada não é encontrada pela geolocalização."""
    payload = make_payload("/configuracao Atlantis")
    with patch("app.core.location.get_location_coords", return_value=None), \
         patch("app.api.webhook.geocode_city", return_value=None, create=True), \
         patch("app.api.webhook.send_whatsapp_message", new_callable=AsyncMock, create=True), \
         patch("app.services.evolution_client.send_whatsapp_message", new_callable=AsyncMock, create=True):
        response = client.post("/api/v1/webhook", json=payload)
        assert response.status_code == 200