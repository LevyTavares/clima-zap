"""Histórico de envios de alertas/boletins (alert_logs).

Dois backends, mesma API: SQLAlchemy (Docker) ou D1 (Workers) —
o interruptor é ``worker_runtime.on_workers()``.

O SQLAlchemy é importado tarde (``app.db.orm``) porque o bundle do Worker não
o empacota.
"""

import app.db.session as db_session
from app.core import worker_runtime
from app.db import d1


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
