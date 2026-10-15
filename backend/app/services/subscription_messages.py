"""Mensagens/respostas de inscrição compartilhadas pelos dois backends.

Usadas por ``app.services.persistence`` (SQLAlchemy) e ``app.db.d1`` (Workers)
para manter exatamente o mesmo contrato de {status, message} — e evitar
código duplicado entre os caminhos.
"""


def already_subscribed(phone: str) -> dict:
    return {
        "status": "already_subscribed",
        "message": f"O número {phone} já se encontra inscrito nos alertas.",
    }


def subscribed(phone: str) -> dict:
    return {
        "status": "success",
        "message": f"Inscrição efetuada com sucesso para o número {phone}.",
    }


def subscription_not_found(phone: str) -> dict:
    return {
        "status": "not_found",
        "message": (
            f"O número {phone} não foi encontrado na base de dados de inscritos."
        ),
    }


def unsubscribed(phone: str) -> dict:
    return {
        "status": "success",
        "message": f"Inscrição cancelada com sucesso para o número {phone}.",
    }
