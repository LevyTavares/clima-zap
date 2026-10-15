"""Adaptador D1 (SQLite no Cloudflare Workers) para as operações de persistência.

Espelha, em SQL puro, o que ``app.services.persistence`` e
``app.services.alert_history`` fazem via SQLAlchemy no caminho Docker/Render.
As funções só são alcançadas quando ``worker_runtime.on_workers()`` é True
(env do Worker anexado com o binding ``DB``).

Conversão JS→Python: o FFI do Pyodide devolve ``JsProxy``; usamos ``to_py()``
quando disponível (no Workers) e dicionários nativos passam direto (testes com
fake). Os objetos ``Subscriber`` retornados são instâncias transitórias do
modelo — os consumidores (dispatcher de alertas) só leem ``phone``/``id``.
"""

import time

from app.core import worker_runtime
from app.models import Subscriber
from app.services import subscription_messages as messages

# Janela de dedupe dos eventos da Evolution (o isolate não guarda estado
# confiável entre requests; usamos a tabela seen_messages no D1).
SEEN_TTL_SECONDS = 1800.0


def _db() -> object:
    database = worker_runtime.d1()
    if database is None:
        raise RuntimeError("Binding D1 (env.DB) indisponível")
    return database


def _to_py(value: object) -> object:
    """Converte JsProxy em estruturas Python; valores nativos passam direto."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    to_py = getattr(value, "to_py", None)
    if callable(to_py):
        return to_py()
    return value


def _rows(result: object) -> list[dict]:
    """Extrai ``result.results`` (lista de dicts) de um D1Result."""
    raw = result["results"] if isinstance(result, dict) else result.results
    return [dict(_to_py(row)) for row in raw]


def _changes(result: object) -> int:
    """Número de linhas afetadas (``meta.changes``) de um D1Result."""
    meta = result["meta"] if isinstance(result, dict) else result.meta
    meta = dict(_to_py(meta))
    return int(meta.get("changes", 0))


def _row_to_subscriber(row: dict) -> Subscriber:
    return Subscriber(
        id=row["id"],
        phone=row["phone"],
        name=row.get("name"),
        city=row.get("city"),
        latitude=row.get("latitude"),
        longitude=row.get("longitude"),
        is_active=bool(row.get("is_active", 0)),
    )


async def find_subscriber(phone: str) -> Subscriber | None:
    """Retorna o assinante (ativo ou não) ou None."""
    result = await _db().prepare(
        "SELECT * FROM subscribers WHERE phone = ?"
    ).bind(phone).all()
    rows = _rows(result)
    return _row_to_subscriber(rows[0]) if rows else None


async def subscribe_recipient(phone: str, name: str | None = None) -> dict:
    """Inscreve ou reativa um destinatário. Retorna {status, message}."""
    clean_name = name.strip() if name and name.strip() else None
    subscriber = await find_subscriber(phone)

    if subscriber is not None and subscriber.is_active:
        return messages.already_subscribed(phone)

    if subscriber is None:
        await _db().prepare(
            "INSERT INTO subscribers (phone, name, is_active) VALUES (?, ?, 1)"
        ).bind(phone, clean_name).run()
    else:
        sets = ["is_active = 1"]
        params: list[object] = []
        if clean_name is not None:
            sets.append("name = ?")
            params.append(clean_name)
        params.append(phone)
        await _db().prepare(
            f"UPDATE subscribers SET {', '.join(sets)} WHERE phone = ?"
        ).bind(*params).run()

    return messages.subscribed(phone)


async def unsubscribe_recipient(phone: str) -> dict:
    """Cancela a inscrição (soft delete). Retorna {status, message}."""
    subscriber = await find_subscriber(phone)

    if subscriber is None or not subscriber.is_active:
        return messages.subscription_not_found(phone)

    await _db().prepare(
        "UPDATE subscribers SET is_active = 0 WHERE phone = ?"
    ).bind(phone).run()
    return messages.unsubscribed(phone)


async def set_subscriber_location(
    phone: str, name: str, latitude: float, longitude: float
) -> None:
    """Grava o local do destinatário (nome + coords); cria o registro se preciso."""
    subscriber = await find_subscriber(phone)

    if subscriber is None:
        await _db().prepare(
            "INSERT INTO subscribers (phone, city, latitude, longitude, is_active)"
            " VALUES (?, ?, ?, ?, 0)"
        ).bind(phone, name, latitude, longitude).run()
    else:
        await _db().prepare(
            "UPDATE subscribers SET city = ?, latitude = ?, longitude = ?"
            " WHERE phone = ?"
        ).bind(name, latitude, longitude, phone).run()


async def clear_subscriber_location(phone: str) -> None:
    """Remove o local definido (volta à região padrão; a inscrição permanece)."""
    await _db().prepare(
        "UPDATE subscribers SET city = NULL, latitude = NULL, longitude = NULL"
        " WHERE phone = ?"
    ).bind(phone).run()


async def should_hint_dm(phone: str) -> bool:
    """True apenas na primeira mensagem sem comando no privado (dica única)."""
    result = await _db().prepare(
        "INSERT OR IGNORE INTO dm_hints (phone, shown_at) VALUES (?, ?)"
    ).bind(phone, time.time()).run()
    return _changes(result) == 1


async def list_active_subscribers() -> list[Subscriber]:
    """Retorna os assinantes ativos (usado pelo dispatcher de alertas)."""
    result = await _db().prepare(
        "SELECT * FROM subscribers WHERE is_active = 1"
    ).all()
    return [_row_to_subscriber(row) for row in _rows(result)]


async def record_alert_dispatch(
    alert_type: str,
    recipient: str,
    delivery_status: str,
    subscriber_id: int | None = None,
) -> None:
    """Registra o envio de um alerta/boletim em alert_logs."""
    await _db().prepare(
        "INSERT INTO alert_logs (alert_type, recipient, delivery_status, subscriber_id)"
        " VALUES (?, ?, ?, ?)"
    ).bind(alert_type, recipient, delivery_status[:32], subscriber_id).run()


async def is_duplicate_message(message_id: str) -> bool:
    """Marca message_id como visto; True se já havia sido visto (duplicado)."""
    database = _db()
    result = await database.prepare(
        "INSERT OR IGNORE INTO seen_messages (message_id, seen_at) VALUES (?, ?)"
    ).bind(message_id, time.time()).run()
    # Limpeza oportunista dos expirados (roda a cada evento deduplicável).
    await database.prepare(
        "DELETE FROM seen_messages WHERE seen_at < ?"
    ).bind(time.time() - SEEN_TTL_SECONDS).run()
    return _changes(result) == 0


async def ping() -> None:
    """Sanidade do banco: ``SELECT 1`` (usado pelo health check)."""
    await _db().prepare("SELECT 1 AS ok").all()
