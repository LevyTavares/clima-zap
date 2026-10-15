"""Entrypoint do Cloudflare Workers: FastAPI (ASGI) + Cron Triggers.

- Requests HTTP  a app FastAPI de ``app.main``; o env do Worker (bindings
  D1/Assets e vars/secrets)  anexado por um middleware em ``app.main``.
- Cron Triggers  os mesmos jobs do APScheduler, disparados pela hora BRT
  (UTC-3) do ``scheduledTime``: alertas 06/08/12/14/16/18h e boletins
  06/14/20h. Sem jitter anti-spam (o isolate no dorme barato).

Deploy (a partir de backend/): ``uv run pywrangler deploy``  veja README.
"""

import logging

import httpx._client as httpx_client
from workers import asgi  # pylint: disable=import-error

# O transporte httpx do Pyodide entrega corpo comprimido sem decodificar
# (workerd fetch + pyfetch)  foramos `Accept-Encoding: identity` para todos
# os clientes (os nossos e os do SDK evolution-whatsapp). Deve rodar antes de
# qualquer httpx.Client/AsyncClient ser criado.
httpx_client.ACCEPT_ENCODING = "identity"

from app.core import worker_runtime  # noqa: E402  pylint: disable=wrong-import-position
from app.main import (  # noqa: E402  pylint: disable=wrong-import-position
    ALERT_SCHEDULE_HOURS,
    FORECAST_PERIOD_BY_HOUR,
    app,
    process_scheduled_weather_alerts,
    send_period_forecast,
)

logger = logging.getLogger("uvicorn.error")

# Reexporta o entrypoint ASGI da FastAPI (fetch/websocket via app.main.app).
_AsgiEntrypoint = asgi.entrypoint(app)


class Default(_AsgiEntrypoint):
    """FastAPI via ASGI + Cron Triggers (alertas e boletins do Cariri)."""

    async def fetch(self, request):
        return await super().fetch(request)

    async def scheduled(self, controller, env, ctx):  # pylint: disable=unused-argument
        """Cron Trigger: dispara jobs pela hora BRT do ``scheduledTime``."""
        worker_runtime.attach(env)
        hour = worker_runtime.brt_hour(controller.scheduledTime)
        logger.warning("Cron Trigger %s  %02dh BRT", controller.cron, hour)

        if hour in ALERT_SCHEDULE_HOURS:
            try:
                await process_scheduled_weather_alerts()
            except Exception as error:  # pylint: disable=broad-exception-caught
                logger.error("Erro no job de alertas (%02dh BRT): %s", hour, error)

        period = FORECAST_PERIOD_BY_HOUR.get(hour)
        if period is not None:
            try:
                await send_period_forecast(period)
            except Exception as error:  # pylint: disable=broad-exception-caught
                logger.error("Erro no boletim %s (%02dh BRT): %s", period, hour, error)
