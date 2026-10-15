"""Gramática de comandos do Clima-Zap.

O bot só reconhece comandos em duas formas de invocação:

1. ``/comando [argumentos]`` — ``/clima``, ``/cidade Crato``;
2. ``@<bot_name> comando [argumentos]`` — ``@clima-zap previsao``.

Menção nativa do WhatsApp também vale como invocação: se o bot está em
``mentionedJid``/``mentionKey`` da mensagem, os tokens ``@...`` iniciais são
removidos e o resto é interpretado como comando (``@5588… clima`` → ``clima``).
Apenas a menção, sem texto, abre o menu.

Qualquer outro texto **não** é comando: em grupo o bot fica calado; no privado
responde uma única vez com a dica de ``/ajuda`` — ver
``app.api.webhook.handle_non_command``.
"""

from typing import NamedTuple

from app.core.config import settings


class Invocation(NamedTuple):
    """Comando reconhecido: nome normalizado (minúsculo, sem '/') + argumentos."""

    command: str
    args: str


def _split_command(body: str) -> Invocation | None:
    """Quebra ``"cidade Crato"`` em (cidade, Crato); None se vazio."""
    body = body.strip()
    if not body:
        return None
    command, _, args = body.partition(" ")
    command = command.lower().strip()
    if not command:
        return None
    return Invocation(command, args.strip())


def _mentions_bot(mentioned_jids: list[str]) -> bool:
    """True se o JID do bot aparece na lista de menções da mensagem."""
    digits = "".join(char for char in settings.target_phone_number if char.isdigit())
    if not digits or not mentioned_jids:
        return False
    # Componente local do JID (antes de "@") — ignora o domínio (s.whatsapp.net).
    # Limitação conhecida: JIDs opacos (@lid) não carregam o número e caem na
    # forma textual "@clima-zap …".
    return any(jid.split("@")[0] == digits for jid in mentioned_jids)


def _literal_mention(text: str) -> Invocation | None:
    """Forma textual ``@<bot_name> comando args`` (sem menção nativa)."""
    name = settings.bot_name.lower().strip().lstrip("@")
    if not name:
        return None
    prefix = f"@{name}"
    if not text.lower().startswith(prefix):
        return None
    boundary = len(prefix)
    # Exige fronteira de palavra: "@clima-zapinho" não invoca o bot.
    if len(text) > boundary and text[boundary] not in " \t":
        return None
    rest = text[boundary:].strip()
    # Menção vazia ("@clima-zap") → menu.
    return _split_command(rest) or Invocation("help", "")


def parse_invocation(
    text: str, mentioned_jids: list[str] | None = None
) -> Invocation | None:
    """Interpreta o texto segundo a gramática; None quando não é comando."""
    text = (text or "").strip()
    if not text:
        return None

    # 1) /comando [args]
    if text.startswith("/"):
        return _split_command(text[1:])

    jids = mentioned_jids or []

    # 2) menção nativa do WhatsApp: strip dos tokens "@…" iniciais → comando
    if _mentions_bot(jids):
        body = text
        while body.startswith("@"):
            _, _, body = body.partition(" ")
            body = body.strip()
        return _split_command(body) or Invocation("help", "")

    # 3) forma textual @<bot_name> comando [args]
    return _literal_mention(text)
