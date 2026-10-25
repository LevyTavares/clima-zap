"""Testes do comando administrativo ``/admin`` (senha, ações e privacidade)."""

import asyncio
import logging

import pytest
from pydantic import SecretStr

from app.api import webhook
from app.api.webhook import route_command
from app.core.config import settings
from app.domain import Subscriber
from app.models import AdminSession, AlertLog  # noqa: F401  pylint: disable=unused-import
from app.schemas.webhook import WebhookPayload
from app.services import admin_commands, admin_sessions
from app.services.alert_history import recent_alert_dispatches, record_alert_dispatch

RECIPIENT = "5588999999999"
GROUP_JID = "120363012345678901@g.us"
PASSWORD = "senha-de-teste-super-secreta"


def run_admin(args: str, recipient: str = RECIPIENT) -> str:
    """Roteia ``/admin <args>`` como o webhook faria."""
    return asyncio.run(route_command("admin", args, recipient))


@pytest.fixture(name="admin_password")
def admin_password_fixture(monkeypatch):
    """Habilita o /admin com senha conhecida e sem allowlist de telefone."""
    monkeypatch.setattr(settings, "admin_password", SecretStr(PASSWORD))
    monkeypatch.setattr(settings, "admin_phone", "")
    return PASSWORD


def test_admin_disabled_when_password_is_empty(monkeypatch):
    monkeypatch.setattr(settings, "admin_password", SecretStr(""))
    monkeypatch.setattr(settings, "admin_phone", "")

    reply = run_admin("qualquer status")

    assert "desabilitada" in reply


def test_admin_rejects_wrong_password(admin_password, monkeypatch):  # pylint: disable=unused-argument
    async def boom():
        raise AssertionError("status não deveria rodar com senha errada")

    monkeypatch.setattr(admin_commands, "check_whatsapp_status", boom)

    reply = run_admin("senha-errada status")

    assert "inválida" in reply
    assert PASSWORD not in reply


def test_admin_phone_allowlist(admin_password, monkeypatch):
    monkeypatch.setattr(settings, "admin_phone", "5511999999999")

    denied = run_admin(f"{admin_password} ping")
    allowed = run_admin(f"{admin_password} ping", recipient="5511999999999")

    assert "não está autorizado" in denied
    assert "pong" in allowed


def test_admin_is_ignored_in_groups(admin_password):
    reply = run_admin(f"{admin_password} ping", recipient=GROUP_JID)

    assert "Comando não reconhecido" in reply
    assert "pong" not in reply


def test_admin_help_lists_actions_without_echoing_password(admin_password):
    reply = run_admin(f"{admin_password} ajuda")

    assert "status" in reply
    assert "boletim" in reply
    assert "alertas" in reply
    assert "register" in reply
    assert "logout" in reply
    assert admin_password not in reply


def test_admin_accepts_extra_spaces(admin_password):
    reply = run_admin(f"  {admin_password}   ping  ")

    assert "pong" in reply


def test_admin_status_shows_monitoring_data(admin_password, monkeypatch):  # pylint: disable=unused-argument
    async def fake_status():
        return {"instance": {"state": "open"}}

    async def fake_subscribers():
        return [
            Subscriber(
                phone=GROUP_JID,
                city="Crato",
                latitude=-7.2342,
                longitude=-39.4086,
                is_active=True,
            ),
            Subscriber(phone=RECIPIENT, is_active=True),
        ]

    async def fake_recent(limit=5):
        assert limit == 5
        return [
            {
                "alert_type": "forecast_night",
                "recipient": GROUP_JID,
                "delivery_status": "sent",
                "sent_at": "2026-10-25 23:00:00",
            }
        ]

    monkeypatch.setattr(admin_commands, "check_whatsapp_status", fake_status)
    monkeypatch.setattr(admin_commands, "list_active_subscribers", fake_subscribers)
    monkeypatch.setattr(admin_commands, "recent_alert_dispatches", fake_recent)

    reply = run_admin(f"{admin_password} status")

    assert "WhatsApp: *open*" in reply
    assert "Assinantes ativos: *2*" in reply
    assert "Crato" in reply
    assert "forecast_night" in reply
    assert "06h, 14h, 20h" in reply


def test_admin_bulletin_triggers_requested_period(admin_password, monkeypatch):
    calls = []

    async def fake_send(period):
        calls.append(period)
        return {"targets": 3, "sent": 2, "failed": 1}

    monkeypatch.setattr("app.main.send_period_forecast", fake_send)

    reply = run_admin(f"{admin_password} boletim manha")

    assert calls == ["morning"]
    assert "2/3" in reply
    assert "Falha(s): 1" in reply


def test_admin_bulletin_without_period_uses_current(admin_password, monkeypatch):
    calls = []

    async def fake_send(period):
        calls.append(period)
        return {"targets": 1, "sent": 1, "failed": 0}

    monkeypatch.setattr("app.main.send_period_forecast", fake_send)

    reply = run_admin(f"{admin_password} boletim")

    assert calls and calls[0] in ("morning", "afternoon", "night")
    assert "1/1" in reply


def test_admin_bulletin_rejects_invalid_period(admin_password):
    reply = run_admin(f"{admin_password} boletim madrugada")

    assert "inválido" in reply


def test_admin_alerts_runs_job(admin_password, monkeypatch):
    called = []

    async def fake_alerts():
        called.append(True)
        return {"locations": 2, "alerts": 3}

    monkeypatch.setattr("app.main.process_scheduled_weather_alerts", fake_alerts)

    reply = run_admin(f"{admin_password} alertas")

    assert called == [True]
    assert "*3*" in reply
    assert "*2*" in reply


def test_admin_groups_lists_subscribed_groups(admin_password, monkeypatch):
    async def fake_groups():
        return [
            Subscriber(
                phone=GROUP_JID,
                city="Crato",
                latitude=-7.2342,
                longitude=-39.4086,
                is_active=True,
            )
        ]

    monkeypatch.setattr(admin_commands, "list_active_groups", fake_groups)

    reply = run_admin(f"{admin_password} grupos")

    assert GROUP_JID in reply
    assert "Crato" in reply


def test_admin_ping(admin_password):
    reply = run_admin(f"{admin_password} ping")

    assert "pong" in reply


def test_admin_register_libera_acoes_por_7_dias(
    admin_password, test_database, monkeypatch
):  # pylint: disable=unused-argument
    async def fake_status():
        return {"instance": {"state": "open"}}

    monkeypatch.setattr(admin_commands, "check_whatsapp_status", fake_status)

    registered = run_admin(f"register {admin_password}")
    ping = run_admin("ping")
    status = run_admin("status")
    logged_out = run_admin("logout")
    after_logout = run_admin("ping")

    assert "Administração liberada" in registered
    assert "7 dias" in registered
    assert admin_password not in registered
    assert "pong" in ping
    assert "Sessão admin: expira em" in status
    assert "encerrada" in logged_out
    assert "Sessão administrativa necessária" in after_logout


def test_admin_register_aceita_prefixo_com_dois_hifens(admin_password, test_database):  # pylint: disable=unused-argument
    reply = run_admin(f"register --{admin_password}")

    assert "Administração liberada" in reply
    assert admin_password not in reply


def test_admin_register_rejeita_senha_errada(admin_password, test_database):  # pylint: disable=unused-argument
    reply = run_admin("register senha-errada")

    assert "inválida" in reply
    assert "Administração liberada" not in reply


def test_admin_acao_sem_sessao_pede_registro(admin_password, test_database):  # pylint: disable=unused-argument
    reply = run_admin("status")

    assert "Sessão administrativa necessária" in reply
    assert "`/admin register <senha>`" in reply


def test_admin_sessao_expirada_nao_autentica(admin_password, test_database):  # pylint: disable=unused-argument
    asyncio.run(
        admin_sessions.register_admin_session(
            RECIPIENT,
            admin_sessions.password_fingerprint(admin_password),
            now=0.0,
        )
    )

    reply = run_admin("ping")

    assert "Sessão administrativa necessária" in reply


def test_admin_troca_de_senha_invalida_sessao(admin_password, test_database):  # pylint: disable=unused-argument
    run_admin(f"register {admin_password}")
    settings.admin_password = SecretStr("outra-senha-administrativa")

    reply = run_admin("ping")

    assert "Sessão administrativa necessária" in reply


def test_admin_password_is_not_written_to_logs(
    admin_password, monkeypatch, caplog
):  # pylint: disable=unused-argument
    async def fake_send(_recipient, _message):
        return {"status": "sent"}

    async def not_duplicate(_message_id):
        return False

    monkeypatch.setattr(webhook, "send_whatsapp_message", fake_send)
    monkeypatch.setattr(webhook, "is_duplicate_message", not_duplicate)

    payload = WebhookPayload(
        event="MESSAGES_UPSERT",
        instance="clima-zap",
        data={
            "key": {
                "remoteJid": f"{RECIPIENT}@s.whatsapp.net",
                "fromMe": False,
                "id": "admin-log-test",
            },
            "message": {"conversation": f"/admin {admin_password} ping"},
        },
    )

    with caplog.at_level(logging.INFO):
        asyncio.run(webhook.process_event_background(payload))

    assert admin_password not in caplog.text
    assert "credenciais omitidas" in caplog.text


def test_admin_password_is_redacted_on_typo(
    admin_password, monkeypatch, caplog
):  # pylint: disable=unused-argument
    async def fake_send(_recipient, _message):
        return {"status": "sent"}

    async def not_duplicate(_message_id):
        return False

    monkeypatch.setattr(webhook, "send_whatsapp_message", fake_send)
    monkeypatch.setattr(webhook, "is_duplicate_message", not_duplicate)

    payload = WebhookPayload(
        event="MESSAGES_UPSERT",
        instance="clima-zap",
        data={
            "key": {
                "remoteJid": f"{RECIPIENT}@s.whatsapp.net",
                "fromMe": False,
                "id": "admin-typo-log-test",
            },
            "message": {"conversation": f"/admn {admin_password} ping"},
        },
    )

    with caplog.at_level(logging.INFO):
        asyncio.run(webhook.process_event_background(payload))

    assert admin_password not in caplog.text
    assert "credenciais omitidas" in caplog.text


def test_recent_alert_dispatches_local(test_database):  # pylint: disable=unused-argument
    async def flow():
        await record_alert_dispatch("forecast_morning", GROUP_JID, "sent")
        await record_alert_dispatch("weather_alert", RECIPIENT, "failed")
        return await recent_alert_dispatches(1)

    rows = asyncio.run(flow())

    assert len(rows) == 1
    assert rows[0]["alert_type"] == "weather_alert"
    assert rows[0]["delivery_status"] == "failed"
