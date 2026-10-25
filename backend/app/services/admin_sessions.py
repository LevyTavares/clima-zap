"""Sessões administrativas de 7 dias, vinculadas ao telefone do WhatsApp.

O ``/admin register <senha>`` autentica uma única vez e grava a sessão; as
demais ações do ``/admin`` passam a valer para aquele número sem repetir a
senha. A sessão é persistida no D1 (Workers) ou no SQLAlchemy (Docker), então
sobrevive a reinícios e a novos isolates.

O ``password_fingerprint`` é o SHA-256 da senha atual: se ``ADMIN_PASSWORD``
mudar, as sessões antigas deixam de autenticar automaticamente. O aviso de
expiração é enviado uma única vez (``notified_at``) pelo job periódico.
"""

from __future__ import annotations

import hashlib
import time

import app.db.session as db_session
from app.core import worker_runtime
from app.db import d1

# Tempo de acesso sem repetir a senha.
ADMIN_SESSION_DAYS = 7
ADMIN_SESSION_SECONDS = ADMIN_SESSION_DAYS * 24 * 60 * 60

EXPIRY_NOTIFICATION_TEXT = (
    "⏰ Sua sessão administrativa do Clima-Zap expirou.\n"
    "Envie `/admin register <senha>` no privado para liberar outro período"
    f" de {ADMIN_SESSION_DAYS} dias."
)


def password_fingerprint(password: str) -> str:
    """SHA-256 da senha administrativa (nunca guardamos a senha em si)."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _now_epoch(now: float | None = None) -> float:
    return time.time() if now is None else now


def _orm():
    """Porta tardia do SQLAlchemy — nunca importada no bundle do Worker."""
    from app.db import orm  # pylint: disable=import-outside-toplevel

    return orm


def _row_to_dict(row) -> dict:
    return {
        "phone": row.phone,
        "password_fingerprint": row.password_fingerprint,
        "registered_at": row.registered_at,
        "expires_at": row.expires_at,
        "notified_at": row.notified_at,
    }


async def register_admin_session(
    phone: str, fingerprint: str, now: float | None = None
) -> float:
    """Cria ou renova a sessão por 7 dias e devolve o ``expires_at`` (epoch).

    Renovar também zera ``notified_at``: o próximo vencimento avisa de novo.
    """
    current = _now_epoch(now)
    expires_at = current + ADMIN_SESSION_SECONDS
    if worker_runtime.on_workers():
        await d1.register_admin_session(phone, fingerprint, current, expires_at)
        return expires_at

    orm = _orm()
    async with db_session.SessionLocal() as session:
        row = await session.get(orm.AdminSession, phone)
        if row is None:
            row = orm.AdminSession(
                phone=phone,
                password_fingerprint=fingerprint,
                registered_at=current,
                expires_at=expires_at,
                notified_at=None,
            )
            session.add(row)
        else:
            row.password_fingerprint = fingerprint
            row.registered_at = current
            row.expires_at = expires_at
            row.notified_at = None
        await session.commit()
    return expires_at


async def get_admin_session(
    phone: str, fingerprint: str, now: float | None = None
) -> dict | None:
    """Sessão ativa do telefone, ou None (expirada/senha trocada/sem registro)."""
    current = _now_epoch(now)
    if worker_runtime.on_workers():
        return await d1.get_admin_session(phone, fingerprint, current)

    orm = _orm()
    async with db_session.SessionLocal() as session:
        result = await session.execute(
            orm.select(orm.AdminSession).where(
                orm.AdminSession.phone == phone,
                orm.AdminSession.password_fingerprint == fingerprint,
                orm.AdminSession.expires_at > current,
            )
        )
        row = result.scalar_one_or_none()
        return _row_to_dict(row) if row is not None else None


async def revoke_admin_session(phone: str) -> bool:
    """Encerra a sessão (``/admin logout``); True se havia uma linha."""
    if worker_runtime.on_workers():
        return await d1.delete_admin_session(phone)

    orm = _orm()
    async with db_session.SessionLocal() as session:
        result = await session.execute(
            orm.delete(orm.AdminSession).where(orm.AdminSession.phone == phone)
        )
        await session.commit()
        return bool(result.rowcount)


async def list_expired_admin_sessions(
    now: float | None = None, limit: int = 50
) -> list[dict]:
    """Sessões vencidas que ainda não receberam o aviso de expiração."""
    current = _now_epoch(now)
    safe_limit = max(1, min(int(limit), 100))
    if worker_runtime.on_workers():
        return await d1.list_expired_admin_sessions(current, safe_limit)

    orm = _orm()
    async with db_session.SessionLocal() as session:
        result = await session.execute(
            orm.select(orm.AdminSession)
            .where(
                orm.AdminSession.expires_at <= current,
                orm.AdminSession.notified_at.is_(None),
            )
            .order_by(orm.AdminSession.expires_at)
            .limit(safe_limit)
        )
        return [_row_to_dict(row) for row in result.scalars()]


async def mark_admin_session_notified(
    phone: str, notified_at: float | None = None
) -> None:
    """Marca o aviso de expiração como enviado (evita mensagem duplicada)."""
    current = _now_epoch(notified_at)
    if worker_runtime.on_workers():
        await d1.mark_admin_session_notified(phone, current)
        return

    orm = _orm()
    async with db_session.SessionLocal() as session:
        row = await session.get(orm.AdminSession, phone)
        if row is not None:
            row.notified_at = current
            await session.commit()
