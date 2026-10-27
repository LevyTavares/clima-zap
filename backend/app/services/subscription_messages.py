"""Mensagens/respostas de inscrição compartilhadas pelos dois backends.

Usadas por ``app.services.persistence`` (SQLAlchemy) e ``app.db.d1`` (Workers)
para manter exatamente o mesmo contrato de {status, message} — e evitar
código duplicado entre os caminhos.
"""

# Tipos de inscrição suportados (inscrição modular).
ALERTS_KIND = "alerts"
BULLETINS_KIND = "bulletins"
ALL_KINDS = {ALERTS_KIND, BULLETINS_KIND}


def _describe(kinds) -> str:
    kinds = set(kinds) if kinds else set(ALL_KINDS)
    if kinds == ALL_KINDS:
        return "alertas e boletins"
    if kinds == {ALERTS_KIND}:
        return "alertas"
    if kinds == {BULLETINS_KIND}:
        return "boletins"
    return ", ".join(sorted(kinds))


def already_subscribed(phone: str, kinds=None) -> dict:
    return {
        "status": "already_subscribed",
        "message": (
            f"O número {phone} já está inscrito em {_describe(kinds)}."
        ),
    }


def subscribed(phone: str, kinds=None) -> dict:
    return {
        "status": "success",
        "message": (
            f"Inscrição efetuada com sucesso em {_describe(kinds)} "
            f"para o número {phone}."
        ),
    }


def subscription_not_found(phone: str) -> dict:
    return {
        "status": "not_found",
        "message": (
            f"O número {phone} não foi encontrado na base de dados de inscritos."
        ),
    }


def unsubscribed(phone: str, kinds=None) -> dict:
    return {
        "status": "success",
        "message": (
            f"Inscrição cancelada em {_describe(kinds)} para o número {phone}."
        ),
    }