"""Persistência de assinantes: inscrição, localização e dedupe.

Compartilhado pela API REST (`POST /api/v1/subscribe`), pelos comandos do
bot (`/inscrever`, `/sair`, `/configuracao`, `/cidade`) e pelo webhook
(dedupe de eventos + dica única no privado).

Dois backends, mesma API:

- CPython (Docker): SQLAlchemy em sessões próprias, no mesmo padrão
  de `app.services.alert_history`.
- Cloudflare Workers: fast-path em D1 (`app/db/d1.py`), ativado quando o
  env do Worker foi anexado (`worker_runtime.on_workers()`).
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import app.db.session as db_session
from app.core import worker_runtime
from app.core.location import LocationData, match_city
from app.db import d1
from app.services import subscription_messages as messages

if TYPE_CHECKING:  # anotação apenas: o ORM não entra no bundle do Worker
    from app.domain import Subscriber

# dedupe: evolution fires per-instance + global webhook → same event twice
_seen_message_ids: dict[str, float] = {}
SEEN_TTL_SECONDS = 300.0

# Dica de /ajuda já mostrada no privado (estado do processo — no Workers a
# tabela dm_hints do D1 faz o papel, já que o isolate não guarda estado).
_dm_hints: set[str] = set()


def _orm():
    """Porta do SQLAlchemy (``app.db.orm``) — import tardio, só no Docker.

    No Workers o SQLAlchemy não está no bundle: qualquer acesso ao ORM acontece
    apenas nos ramos em que ``worker_runtime.on_workers()`` é False.
    """
    from app.db import orm  # pylint: disable=import-outside-toplevel

    return orm


async def _find_subscriber(session, phone: str) -> Subscriber | None:
    orm = _orm()
    result = await session.execute(
        orm.select(orm.Subscriber).where(orm.Subscriber.phone == phone)
    )
    return result.scalar_one_or_none()


def _subscriber_location(subscriber: Subscriber | None) -> LocationData | None:
    """Coords salvas > cidade preset legada > None (região padrão)."""
    if subscriber is None:
        return None
    if subscriber.latitude is not None and subscriber.longitude is not None:
        return {
            "name": subscriber.city
            or f"{subscriber.latitude:g}, {subscriber.longitude:g}",
            "latitude": float(subscriber.latitude),
            "longitude": float(subscriber.longitude),
        }
    if subscriber.city:
        return match_city(subscriber.city)
    return None


async def get_subscriber_location(phone: str) -> LocationData | None:
    """Local do destinatário ou None (região padrão da aplicação)."""
    if worker_runtime.on_workers():
        subscriber = await d1.find_subscriber(phone)
    else:
        async with db_session.SessionLocal() as session:
            subscriber = await _find_subscriber(session, phone)
    return _subscriber_location(subscriber)


async def subscribe_recipient(phone: str, name: str | None = None) -> dict:
    """Inscreve ou reativa um destinatário. Retorna {status, message}."""
    if worker_runtime.on_workers():
        return await d1.subscribe_recipient(phone, name)
    async with db_session.SessionLocal() as session:
        subscriber = await _find_subscriber(session, phone)

        if subscriber and subscriber.is_active:
            return messages.already_subscribed(phone)

        if subscriber:
            subscriber.is_active = True
            if name is not None:
                subscriber.name = name.strip() or None
        else:
            session.add(
                _orm().Subscriber(
                    phone=phone, name=name.strip() if name else None
                )
            )
        await session.commit()
        return messages.subscribed(phone)


async def unsubscribe_recipient(phone: str) -> dict:
    """Cancela a inscrição (soft delete). Retorna {status, message}."""
    if worker_runtime.on_workers():
        return await d1.unsubscribe_recipient(phone)
    async with db_session.SessionLocal() as session:
        subscriber = await _find_subscriber(session, phone)

        if subscriber is None or not subscriber.is_active:
            return messages.subscription_not_found(phone)

        subscriber.is_active = False
        await session.commit()
        return messages.unsubscribed(phone)


async def set_subscriber_location(
    phone: str, name: str, latitude: float, longitude: float
) -> None:
    """Grava o local do destinatário (nome + coords); cria o registro se preciso."""
    if worker_runtime.on_workers():
        await d1.set_subscriber_location(phone, name, latitude, longitude)
        return
    async with db_session.SessionLocal() as session:
        subscriber = await _find_subscriber(session, phone)

        if subscriber is None:
            subscriber = _orm().Subscriber(phone=phone, is_active=False)
            session.add(subscriber)
        subscriber.city = name
        subscriber.latitude = latitude
        subscriber.longitude = longitude
        await session.commit()


async def clear_subscriber_location(phone: str) -> None:
    """Remove o local definido (volta à região padrão; a inscrição permanece)."""
    if worker_runtime.on_workers():
        await d1.clear_subscriber_location(phone)
        return
    async with db_session.SessionLocal() as session:
        subscriber = await _find_subscriber(session, phone)

        if subscriber is not None:
            subscriber.city = None
            subscriber.latitude = None
            subscriber.longitude = None
            await session.commit()


async def should_hint_dm(phone: str) -> bool:
    """True apenas na primeira mensagem sem comando no privado (dica única)."""
    if worker_runtime.on_workers():
        return await d1.should_hint_dm(phone)
    if phone in _dm_hints:
        return False
    _dm_hints.add(phone)
    return True


async def list_active_subscribers() -> list[Subscriber]:
    """Retorna os assinantes ativos (usado pelo dispatcher de alertas)."""
    if worker_runtime.on_workers():
        return await d1.list_active_subscribers()
    async with db_session.SessionLocal() as session:
        orm = _orm()
        result = await session.execute(
            orm.select(orm.Subscriber).where(orm.Subscriber.is_active.is_(True))
        )
        return list(result.scalars())


async def group_active_subscribers_by_city() -> dict[str, list[Subscriber]]:
    """Agrupa assinantes ativos por cidade ('' = região padrão)."""
    groups: dict[str, list[Subscriber]] = {}
    for subscriber in await list_active_subscribers():
        groups.setdefault(subscriber.city or "", []).append(subscriber)
    return groups


def resolve_group_location(
    city: str, subscribers: list[Subscriber]
) -> LocationData | None:
    """Local de um grupo de alertas: coords do primeiro assinante que tiver,
    senão o preset da cidade ('' = região padrão → None)."""
    for subscriber in subscribers:
        if subscriber.latitude is not None and subscriber.longitude is not None:
            return {
                "name": subscriber.city or city,
                "latitude": float(subscriber.latitude),
                "longitude": float(subscriber.longitude),
            }
    return match_city(city) if city else None


async def is_duplicate_message(message_id: str) -> bool:
    """Marca a mensagem como vista. True = duplicado (já processado).

    No Workers o estado vive na tabela ``seen_messages`` (D1); localmente
    usamos o cache em memória do isolate.
    """
    if worker_runtime.on_workers():
        return await d1.is_duplicate_message(message_id)

    now = time.monotonic()
    expired = [
        key
        for key, seen_at in _seen_message_ids.items()
        if now - seen_at > SEEN_TTL_SECONDS
    ]
    for key in expired:
        _seen_message_ids.pop(key, None)
    if message_id in _seen_message_ids:
        return True
    _seen_message_ids[message_id] = now
    return False
