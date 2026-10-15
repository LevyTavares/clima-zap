"""Testes da gramática do bot no webhook, do roteador e da autenticação.

Comandos só valem como ``/comando`` ou ``@clima-zap comando`` (ver
``app.services.command_parser``); texto solto é silenciado em grupo e gera a
dica única de ``/ajuda`` no privado.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.webhook import handle_non_command, recipient_key, route_command
from app.core.config import settings
from app.main import app
from app.models import Subscriber
from app.services.command_parser import parse_invocation

client = TestClient(app)
RECIPIENT = "5588999999999"


def run(coro):
    return asyncio.run(coro)


def run_command(text, recipient=RECIPIENT, mentioned_jids=None):
    """Parseia o texto pela gramática e roteia — atalho dos testes."""
    invocation = parse_invocation(text, mentioned_jids)
    assert invocation is not None, f"não era comando: {text!r}"
    return run(route_command(invocation.command, invocation.args, recipient))


def read_location(db_session, phone):
    async def query():
        async with db_session() as session:
            result = await session.execute(
                select(Subscriber).where(Subscriber.phone == phone)
            )
            subscriber = result.scalar_one()
            return subscriber.city, subscriber.latitude, subscriber.longitude

    return run(query())


def test_recipient_key_handles_dm_and_group():
    assert recipient_key("5588999999999@s.whatsapp.net") == "5588999999999"
    assert recipient_key("120363012345678901@g.us") == "120363012345678901@g.us"


def test_help_command_returns_bot_menu():
    reply = run_command("/ajuda")

    assert "*/ajuda*" in reply
    assert "*/cidade <nome>*" in reply
    assert "*/configuracao" in reply
    assert "*/inscrever*" in reply


def test_unknown_command_suggests_menu():
    reply = run_command("/foo")

    assert "Comando não reconhecido" in reply
    assert "/ajuda" in reply


def test_set_and_show_city(test_database):
    set_reply = run_command("/cidade crato")
    assert "*Crato*" in set_reply

    show_reply = run_command("/cidade")
    assert "*Crato*" in show_reply
    assert "/configuracao" in show_reply

    city, latitude, longitude = read_location(test_database, RECIPIENT)
    assert city == "Crato"
    assert latitude == pytest.approx(-7.2342)
    assert longitude == pytest.approx(-39.4086)

    async def read_is_active():
        async with test_database() as session:
            result = await session.execute(
                select(Subscriber).where(Subscriber.phone == RECIPIENT)
            )
            return result.scalar_one().is_active

    assert run(read_is_active()) is False  # /cidade não ativa os alertas sozinho


def test_configuracao_with_coordinates(test_database):
    set_reply = run_command("/configuracao -7.23,-39.31")
    assert "*-7.23, -39.31*" in set_reply

    show_reply = run_command("/configuracao")
    assert "*-7.23, -39.31*" in show_reply

    city, latitude, longitude = read_location(test_database, RECIPIENT)
    assert city == "-7.23, -39.31"
    assert latitude == pytest.approx(-7.23)
    assert longitude == pytest.approx(-39.31)


def test_configuracao_reset_returns_to_default(test_database):
    run_command("/cidade crato")
    reset_reply = run_command("/configuracao padrao")

    assert "padrão" in reset_reply

    city, latitude, longitude = read_location(test_database, RECIPIENT)
    assert (city, latitude, longitude) == (None, None, None)

    show_reply = run_command("/configuracao")
    assert "Nenhum local definido" in show_reply


def test_configuracao_geocodes_cities_outside_presets(test_database, monkeypatch):
    async def fake_geocode(query):
        assert query == "fortaleza"
        return {"name": "Fortaleza, Ceará", "latitude": -3.73, "longitude": -38.53}

    monkeypatch.setattr("app.api.webhook.geocode_city", fake_geocode)

    reply = run_command("/configuracao fortaleza")
    assert "*Fortaleza, Ceará*" in reply

    city, latitude, longitude = read_location(test_database, RECIPIENT)
    assert city == "Fortaleza, Ceará"
    assert latitude == pytest.approx(-3.73)
    assert longitude == pytest.approx(-38.53)


def test_unknown_local_lists_options_when_geocode_misses(monkeypatch):
    async def fake_geocode(_query):
        return None

    monkeypatch.setattr("app.api.webhook.geocode_city", fake_geocode)

    reply = run_command("/configuracao Atlantis")

    assert "não encontrado" in reply
    assert "Barbalha" in reply
    assert "coordenadas" in reply


def test_subscribe_and_leave_cycle(test_database):
    first = run_command("/inscrever")
    assert "Inscrição realizada" in first

    again = run_command("/inscrever")
    assert "já está inscrito" in again

    left = run_command("/sair")
    assert "cancelada" in left

    left_again = run_command("/sair")
    assert "não possui inscrição" in left_again

    async def read_is_active():
        async with test_database() as session:
            result = await session.execute(
                select(Subscriber).where(Subscriber.phone == RECIPIENT)
            )
            return result.scalar_one().is_active

    assert run(read_is_active()) is False


def test_forecast_uses_subscriber_location(test_database, monkeypatch):
    captured = {}

    async def fake_forecast(location=None):
        captured["location"] = location
        return "previsao-ok"

    monkeypatch.setattr("app.api.webhook.build_current_forecast", fake_forecast)

    run_command("/cidade crato")
    reply = run_command("/clima")

    assert reply == "previsao-ok"
    assert captured["location"]["name"] == "Crato"
    assert captured["location"]["latitude"] == pytest.approx(-7.2342)

    city, _, _ = read_location(test_database, RECIPIENT)
    assert city == "Crato"


@pytest.mark.usefixtures("test_database")
def test_forecast_defaults_to_region_without_city(monkeypatch):
    captured = {}

    async def fake_forecast(location=None):
        captured["location"] = location
        return "previsao-ok"

    monkeypatch.setattr("app.api.webhook.build_current_forecast", fake_forecast)

    reply = run_command("/previsão", "5588000000000")

    assert reply == "previsao-ok"
    assert captured["location"] is None


# ---------------------------------------------------------------------------
# Texto sem comando: silêncio em grupo, dica única no privado
# ---------------------------------------------------------------------------


def test_non_command_in_group_stays_silent():
    assert run(handle_non_command("120363012345678901@g.us")) is None


def test_non_command_dm_hints_only_once():
    phone = "5588777777777"  # telefone único entre testes (estado em memória)

    first = run(handle_non_command(phone))
    second = run(handle_non_command(phone))

    assert first is not None
    assert "/ajuda" in first
    assert second is None


# ---------------------------------------------------------------------------
# Fluxo completo webhook → resposta (e auth)
# ---------------------------------------------------------------------------


def test_webhook_end_to_end_reply(monkeypatch):
    sent = {}

    async def fake_send(number, message):
        sent["number"] = number
        sent["message"] = message
        return {"status": "sent"}

    monkeypatch.setattr("app.api.webhook.send_whatsapp_message", fake_send)

    payload = {
        "event": "MESSAGES_UPSERT",
        "instance": "clima-zap",
        "data": {
            "key": {
                "remoteJid": "5588111111111@s.whatsapp.net",
                "fromMe": False,
                "id": "TEST-E2E-1",
            },
            "message": {"conversation": "/ajuda"},
        },
    }
    response = client.post("/api/v1/webhook", json=payload)

    assert response.status_code == 200
    assert sent["number"] == "5588111111111"
    assert "*/ajuda*" in sent["message"]


def test_webhook_non_command_in_group_gets_no_reply(monkeypatch):
    sent = []

    async def fake_send(number, message):
        sent.append((number, message))
        return {"status": "sent"}

    monkeypatch.setattr("app.api.webhook.send_whatsapp_message", fake_send)

    payload = {
        "event": "MESSAGES_UPSERT",
        "instance": "clima-zap",
        "data": {
            "key": {
                "remoteJid": "120363055555555@g.us",
                "fromMe": False,
                "id": "TEST-GROUP-SILENT-1",
            },
            "message": {"conversation": "bom dia a todos"},
        },
    }
    response = client.post("/api/v1/webhook", json=payload)

    assert response.status_code == 200
    assert not sent


def test_webhook_non_command_dm_gets_hint_only_once(monkeypatch):
    sent = []

    async def fake_send(number, message):
        sent.append((number, message))
        return {"status": "sent"}

    monkeypatch.setattr("app.api.webhook.send_whatsapp_message", fake_send)

    def payload(message_id):
        return {
            "event": "MESSAGES_UPSERT",
            "instance": "clima-zap",
            "data": {
                "key": {
                    "remoteJid": "5588444444444@s.whatsapp.net",
                    "fromMe": False,
                    "id": message_id,
                },
                "message": {"conversation": "oi, tudo bem?"},
            },
        }

    assert client.post("/api/v1/webhook", json=payload("TEST-DM-HINT-1")).status_code == 200
    assert client.post("/api/v1/webhook", json=payload("TEST-DM-HINT-2")).status_code == 200

    assert len(sent) == 1
    assert "/ajuda" in sent[0][1]


def test_webhook_native_mention_runs_command(monkeypatch):
    monkeypatch.setattr(settings, "target_phone_number", "5588000000000")
    sent = []

    async def fake_send(number, message):
        sent.append((number, message))
        return {"status": "sent"}

    monkeypatch.setattr("app.api.webhook.send_whatsapp_message", fake_send)

    payload = {
        "event": "MESSAGES_UPSERT",
        "instance": "clima-zap",
        "data": {
            "key": {
                "remoteJid": "5588123456789@s.whatsapp.net",
                "fromMe": False,
                "id": "TEST-MENTION-1",
            },
            "message": {
                "extendedTextMessage": {
                    "text": "@5588000000000 ajuda",
                    "contextInfo": {"mentionedJid": ["5588000000000@s.whatsapp.net"]},
                }
            },
        },
    }
    response = client.post("/api/v1/webhook", json=payload)

    assert response.status_code == 200
    assert len(sent) == 1
    assert "*/ajuda*" in sent[0][1]


def test_webhook_open_when_token_unset(monkeypatch):
    monkeypatch.setattr(settings, "webhook_auth_token", "")

    response = client.post(
        "/api/v1/webhook", json={"event": "PING", "instance": "clima-zap"}
    )

    assert response.status_code == 200


def test_webhook_requires_bearer_token_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "webhook_auth_token", "s3cret")
    payload = {"event": "PING", "instance": "clima-zap"}

    denied = client.post("/api/v1/webhook", json=payload)
    assert denied.status_code == 401

    wrong = client.post(
        "/api/v1/webhook",
        json=payload,
        headers={"Authorization": "Bearer errado"},
    )
    assert wrong.status_code == 401

    allowed = client.post(
        "/api/v1/webhook",
        json=payload,
        headers={"Authorization": "Bearer s3cret"},
    )
    assert allowed.status_code == 200
