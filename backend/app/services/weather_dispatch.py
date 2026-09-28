import logging

from evolution_api import EvolutionError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

import app.db.session as db_session
from app.models import Subscriber
from app.services.alert_history import record_alert_dispatch
from app.services.evolution_client import send_whatsapp_message

logger = logging.getLogger("uvicorn.error")


async def dispatch_weather_alerts(alerts: list[str]) -> None:
    """Send generated weather alerts to active subscribers and persist outcomes."""
    if not alerts:
        return

    try:
        async with db_session.SessionLocal() as session:
            result = await session.execute(
                select(Subscriber).where(Subscriber.is_active.is_(True))
            )
            subscribers = list(result.scalars())
    except SQLAlchemyError as error:
        logger.error("Erro ao buscar assinantes ativos para alerta: %s", error)
        return

    for subscriber in subscribers:
        for alert in alerts:
            status = "sent"
            try:
                response = await send_whatsapp_message(subscriber.phone, alert)
                if isinstance(response, dict):
                    status = str(response.get("status", status))
            except EvolutionError as error:
                status = "failed"
                logger.error(
                    "Erro ao enviar alerta climático para %s: %s",
                    subscriber.phone,
                    error,
                )

            try:
                await record_alert_dispatch(
                    "weather_alert",
                    subscriber.phone,
                    status,
                    subscriber.id,
                )
            except SQLAlchemyError as error:
                logger.error(
                    "Erro ao registrar alerta climático para %s: %s",
                    subscriber.phone,
                    error,
                )