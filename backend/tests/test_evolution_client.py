"""Travas de envio do cliente de WhatsApp.

Fora de produção o envio fica bloqueado por padrão; um backend local não pode
responder na mesma instância/número usado pelo Worker.
"""

import asyncio

from app.core.config import settings
from app.services import evolution_client


def test_envio_bloqueado_por_default_fora_de_producao(monkeypatch, caplog):
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "allow_outbound", None)

    def boom():
        raise AssertionError("não deveria criar cliente")

    monkeypatch.setattr(evolution_client, "get_evolution_client", boom)

    result = asyncio.run(
        evolution_client.send_whatsapp_message("558899999999", "olá")
    )

    assert result == {"status": "blocked", "reason": "outbound_disabled"}
    assert "Envio WhatsApp bloqueado" in caplog.text


def test_envio_permitido_em_producao(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "allow_outbound", None)
    sent = {}

    class FakeClient:
        async def send_text(self, number, message):
            sent["number"] = number
            sent["message"] = message
            return {"status": "PENDING"}

    monkeypatch.setattr(evolution_client, "get_evolution_client", FakeClient)

    result = asyncio.run(
        evolution_client.send_whatsapp_message("558899999999", "olá")
    )

    assert result == {"status": "PENDING"}
    assert sent == {"number": "558899999999", "message": "olá"}


def test_envio_permitido_com_override_explicito_em_dev(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "allow_outbound", True)
    sent = {}

    class FakeClient:
        async def send_text(self, number, message):
            sent["number"] = number
            sent["message"] = message
            return {"status": "PENDING"}

    monkeypatch.setattr(evolution_client, "get_evolution_client", FakeClient)

    result = asyncio.run(
        evolution_client.send_whatsapp_message("558899999999", "olá")
    )

    assert result == {"status": "PENDING"}
    assert sent == {"number": "558899999999", "message": "olá"}
