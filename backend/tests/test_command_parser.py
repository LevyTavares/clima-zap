"""Testes da gramática de invocação do bot (app.services.command_parser).

As duas formas válidas: ``/comando`` e ``@botname comando`` (mais a menção
nativa do WhatsApp). Texto solto não é comando.
"""

import pytest

from app.core.config import settings
from app.services.command_parser import parse_invocation

BOT_JID = "5588000000000@s.whatsapp.net"


@pytest.fixture(autouse=True)
def bot_identity(monkeypatch):
    """Identidade do bot usada nas formas de menção (nativa e textual)."""
    monkeypatch.setattr(settings, "target_phone_number", "+5588000000000")
    monkeypatch.setattr(settings, "bot_name", "clima-zap")


def test_slash_form_parses_command_and_args():
    assert parse_invocation("/Ajuda ") == ("ajuda", "")
    assert parse_invocation("  /CLIMA") == ("clima", "")
    assert parse_invocation("/cidade Crato") == ("cidade", "Crato")
    assert parse_invocation("/configuracao -7.23,-39.31") == (
        "configuracao",
        "-7.23,-39.31",
    )
    assert parse_invocation("/?") == ("?", "")
    assert parse_invocation("/") is None
    assert parse_invocation("") is None


def test_bare_text_is_not_a_command():
    assert parse_invocation("ajuda") is None
    assert parse_invocation("inscrever") is None
    assert parse_invocation("previsão do tempo") is None
    assert parse_invocation("   ") is None
    # menção de outro contato não vira invocação
    assert parse_invocation("clima", ["5588111111111@s.whatsapp.net"]) is None


def test_literal_mention_form():
    assert parse_invocation("@clima-zap previsao") == ("previsao", "")
    assert parse_invocation("@Clima-Zap cidade Crato") == ("cidade", "Crato")
    # menção vazia abre o menu
    assert parse_invocation("@clima-zap") == ("help", "")
    # fronteira de palavra: sufixo colado não invoca o bot
    assert parse_invocation("@clima-zapinho clima") is None


def test_native_mention_form():
    mentioned = [BOT_JID]
    assert parse_invocation("@5588000000000 clima", mentioned) == ("clima", "")
    assert parse_invocation("@5588000000000 previsao", mentioned) == (
        "previsao",
        "",
    )
    # só a menção → menu
    assert parse_invocation("@5588000000000", mentioned) == ("help", "")
    # menção nativa dispensa o "@" inicial: bot mencionado + texto é comando
    assert parse_invocation("clima", mentioned) == ("clima", "")
    # sem o bot nas menções, "@número ..." não é invocação
    assert parse_invocation("@5588000000000 clima", ["5588999999999@s.whatsapp.net"]) is None
