"""Testes das sessões administrativas de 7 dias e do aviso de expiração."""

import asyncio

import app.main as main_module
from app.models import AdminSession  # noqa: F401  pylint: disable=unused-import
from app.services import admin_sessions

PHONE = "5588999999999"
FINGERPRINT = admin_sessions.password_fingerprint("senha-de-teste")


def test_sessao_registrada_renovada_e_encerrada(test_database):  # pylint: disable=unused-argument
    async def flow():
        expires = await admin_sessions.register_admin_session(
            PHONE, FINGERPRINT, now=1_000.0
        )
        active = await admin_sessions.get_admin_session(
            PHONE, FINGERPRINT, now=1_001.0
        )
        wrong_password = await admin_sessions.get_admin_session(
            PHONE, "outro-fingerprint", now=1_001.0
        )
        expired = await admin_sessions.get_admin_session(
            PHONE,
            FINGERPRINT,
            now=1_000.0 + admin_sessions.ADMIN_SESSION_SECONDS + 1,
        )
        revoked = await admin_sessions.revoke_admin_session(PHONE)
        after_revoke = await admin_sessions.get_admin_session(
            PHONE, FINGERPRINT, now=1_001.0
        )
        return expires, active, wrong_password, expired, revoked, after_revoke

    expires, active, wrong_password, expired, revoked, after_revoke = asyncio.run(
        flow()
    )

    assert expires == 1_000.0 + admin_sessions.ADMIN_SESSION_SECONDS
    assert active["phone"] == PHONE
    assert wrong_password is None
    assert expired is None
    assert revoked is True
    assert after_revoke is None


def test_novo_registro_renova_prazo_e_limpa_aviso(test_database):  # pylint: disable=unused-argument
    async def flow():
        await admin_sessions.register_admin_session(PHONE, FINGERPRINT, now=0.0)
        await admin_sessions.mark_admin_session_notified(PHONE, notified_at=10.0)
        before = await admin_sessions.list_expired_admin_sessions(now=20.0)
        expires = await admin_sessions.register_admin_session(
            PHONE, FINGERPRINT, now=1_000.0
        )
        session = await admin_sessions.get_admin_session(
            PHONE, FINGERPRINT, now=1_000.0
        )
        return before, expires, session

    before, expires, session = asyncio.run(flow())

    assert before == []
    assert expires == 1_000.0 + admin_sessions.ADMIN_SESSION_SECONDS
    assert session["notified_at"] is None


def test_process_expired_envia_aviso_uma_vez(test_database, monkeypatch):  # pylint: disable=unused-argument
    sent = []

    async def fake_send(phone, message):
        sent.append((phone, message))
        return {"status": "sent"}

    monkeypatch.setattr(main_module, "send_whatsapp_message", fake_send)
    asyncio.run(
        admin_sessions.register_admin_session(PHONE, FINGERPRINT, now=0.0)
    )

    first = asyncio.run(main_module.process_expired_admin_sessions())
    second = asyncio.run(main_module.process_expired_admin_sessions())

    assert first == {"expired": 1, "notified": 1, "failed": 0}
    assert second == {"expired": 0, "notified": 0, "failed": 0}
    assert sent == [
        (PHONE, admin_sessions.EXPIRY_NOTIFICATION_TEXT)
    ]


def test_process_expired_tenta_de_novo_quando_envio_falha(test_database, monkeypatch):  # pylint: disable=unused-argument
    async def failing_send(_phone, _message):
        raise RuntimeError("Evolution indisponível")

    monkeypatch.setattr(main_module, "send_whatsapp_message", failing_send)
    asyncio.run(
        admin_sessions.register_admin_session(PHONE, FINGERPRINT, now=0.0)
    )

    failed = asyncio.run(main_module.process_expired_admin_sessions())

    assert failed == {"expired": 1, "notified": 0, "failed": 1}

    sent = []

    async def fake_send(phone, message):
        sent.append((phone, message))
        return {"status": "sent"}

    monkeypatch.setattr(main_module, "send_whatsapp_message", fake_send)
    retried = asyncio.run(main_module.process_expired_admin_sessions())

    assert retried == {"expired": 1, "notified": 1, "failed": 0}
    assert sent == [(PHONE, admin_sessions.EXPIRY_NOTIFICATION_TEXT)]
