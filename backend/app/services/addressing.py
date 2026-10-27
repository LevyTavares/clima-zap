"""Auxiliares de tratamento (singular/plural) conforme o destinatário.

Em grupos (JID terminando em ``@g.us``) o bot fala no plural; no privado,
no singular.
"""


def is_group(recipient: str | None) -> bool:
    return bool(recipient) and str(recipient).endswith("@g.us")


def you(recipient: str | None) -> str:
    return "vocês" if is_group(recipient) else "você"


def your(recipient: str | None) -> str:
    return "seus" if is_group(recipient) else "seu"


def plural_suffix(recipient: str | None) -> str:
    return "s" if is_group(recipient) else ""