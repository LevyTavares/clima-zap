import logging

from evolution_api import EvolutionError
from sqlalchemy.exc import SQLAlchemyError

from app.models import Subscriber
from app.services.alert_history import record_alert_dispatch
from app.services.evolution_client import send_whatsapp_message
from app.services.persistence import list_active_subscribers

logger = logging.getLogger("uvicorn.error")


async def dispatch_weather_alerts(
    alerts: list[str],
    subscribers: list[Subscriber] | None = None,
) -> None:
    """Send generated weather alerts to subscribers and persist outcomes.

    subscribers: lista explícita (ex: assinantes de uma cidade). Quando None,
    busca todos os assinantes ativos.
    """
    if not alerts:
        return

    if subscribers is None:
        try:
            subscribers = await list_active_subscribers()
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
