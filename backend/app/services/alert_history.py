"""Histórico de envios de alertas/boletins (alert_logs).

Dois backends, mesma API: SQLAlchemy (Docker) ou D1 (Workers) —
o interruptor é ``worker_runtime.on_workers()``.

O SQLAlchemy é importado tarde (``app.db.orm``) porque o bundle do Worker não
o empacota; a retenção do histórico (``prune_alert_logs``) roda todo dia no
agendamento da noite (``app.core.schedule.MAINTENANCE_HOUR``).
"""

from datetime import datetime, timedelta, timezone

import app.db.session as db_session
from app.core import worker_runtime
from app.db import d1

# Retenção do histórico de envios (evita crescer para sempre no D1/Postgres).
ALERT_LOG_RETENTION_DAYS = 90


async def record_alert_dispatch(
    alert_type: str,
    recipient: str,
    delivery_status: str,
    subscriber_id: int | None = None,
) -> None:
    if worker_runtime.on_workers():
        await d1.record_alert_dispatch(
            alert_type, recipient, delivery_status, subscriber_id
        )
        return
    from app.db.orm import AlertLog  # pylint: disable=import-outside-toplevel

    async with db_session.SessionLocal() as session:
        session.add(
            AlertLog(
                alert_type=alert_type,
                recipient=recipient,
                delivery_status=delivery_status[:32],
                subscriber_id=subscriber_id,
            )
        )
        await session.commit()


async def prune_alert_logs(days: int = ALERT_LOG_RETENTION_DAYS) -> int:
    """Apaga os envios mais antigos que ``days``; devolve quantas linhas saíram."""
    if worker_runtime.on_workers():
        return await d1.prune_alert_logs(days)
    from app.db.orm import AlertLog, delete  # pylint: disable=import-outside-toplevel

    # cutoff consciente de fuso (Postgres timestamptz); no SQLite o offset é
    # descartado e comparamos string UTC com string UTC (default da tabela).
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    async with db_session.SessionLocal() as session:
        result = await session.execute(
            delete(AlertLog).where(AlertLog.sent_at < cutoff)
        )
        await session.commit()
        return int(result.rowcount or 0)
