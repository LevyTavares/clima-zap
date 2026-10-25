"""Entrypoint do Cloudflare Workers: FastAPI (ASGI) + Cron Triggers.

- Requests HTTP → a app FastAPI de ``app.main``; o env do Worker (bindings
  D1/Assets e vars/secrets) é anexado por um middleware em ``app.main``.
- Cron Triggers → os mesmos jobs do APScheduler, disparados pela hora BRT
  (UTC-3) do ``scheduledTime``: alertas 06/08/12/14/16/18h e boletins
  06/14/20h. Cada expressão dispara só o seu job (as duas coincidem em 06h e
  14h) e o boletim dorme o mesmo jitter anti-spam 0–15min do caminho Docker —
  por isso o sorteio respeita o limite de 15min de wall time do Cron Trigger
  (``app.core.schedule``). Em 20h BRT roda também o purge do histórico. O cron
  ``*/5 * * * *`` avisa quando uma sessão administrativa de 7 dias expira.

Deploy (a partir de backend/): ``uv run pywrangler deploy`` — veja README.
"""

import asyncio
import logging

import httpx._client as httpx_client
from workers import asgi  # pylint: disable=import-error

# O transporte httpx do Pyodide entrega corpo comprimido sem decodificar
# (workerd fetch + pyfetch) — forçamos `Accept-Encoding: identity` para todos
# os clientes (os nossos e os do SDK evolution-whatsapp). Deve rodar antes de
# qualquer httpx.Client/AsyncClient ser criado.
httpx_client.ACCEPT_ENCODING = "identity"

from app.core import worker_runtime  # noqa: E402  pylint: disable=wrong-import-position
from app.core.schedule import (  # noqa: E402  pylint: disable=wrong-import-position
    ALERT_SCHEDULE_HOURS,
    FORECAST_JITTER_SECONDS,
    FORECAST_PERIOD_BY_HOUR,
    MAINTENANCE_HOUR,
    cron_dispatch,
    is_admin_session_cron,
    jitter_delay_seconds,
)
from app.main import (  # noqa: E402  pylint: disable=wrong-import-position
    app,
    process_expired_admin_sessions,
    process_scheduled_weather_alerts,
    send_period_forecast,
)
from app.services.alert_history import (  # noqa: E402  pylint: disable=wrong-import-position
    prune_alert_logs,
)
from app.services.forecast import Period  # noqa: E402  pylint: disable=wrong-import-position

logger = logging.getLogger("uvicorn.error")

# Reexporta o entrypoint ASGI da FastAPI (fetch/websocket via app.main.app).
_AsgiEntrypoint = asgi.entrypoint(app)


class Default(_AsgiEntrypoint):
    """FastAPI via ASGI + Cron Triggers (alertas e boletins do Cariri)."""

    async def fetch(self, request):
        return await super().fetch(request)

    async def scheduled(self, controller, env, ctx):  # pylint: disable=unused-argument
        """Cron Trigger: dispara os jobs devidos pela expressão e hora BRT."""
        # O runtime do Cron Trigger nem sempre entrega o `env` no argumento:
        # na versão fixada pela compatibility_date do deploy ele chega None
        # (o `--latest` do `wrangler dev` mascara isso). O `WorkerEntrypoint`
        # guarda o env real em `self.env`; sem ele o `attach` não ativa o
        # caminho D1 e o job cai no ramo SQLAlchemy, que não existe no bundle.
        worker_runtime.attach(worker_runtime.scheduled_env(self, env))
        cron = (controller.cron or "").strip()
        hour = worker_runtime.brt_hour(controller.scheduledTime)
        alerts_due, bulletins_due = cron_dispatch(cron)
        if alerts_due or bulletins_due:
            logger.warning("Cron Trigger %s → %02dh BRT", cron, hour)

        if is_admin_session_cron(cron):
            await self._notify_expired_admin_sessions()

        if alerts_due and hour in ALERT_SCHEDULE_HOURS:
            await self._send_alerts(hour)

        if bulletins_due and hour == MAINTENANCE_HOUR:
            await self._prune_history()

        period = FORECAST_PERIOD_BY_HOUR.get(hour) if bulletins_due else None
        if period is not None:
            await self._send_bulletin(period)

    @staticmethod
    async def _notify_expired_admin_sessions() -> None:
        """Avisa no WhatsApp as sessões administrativas que venceram."""
        try:
            await process_expired_admin_sessions()
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Erro no aviso de sessão administrativa expirada")

    @staticmethod
    async def _prune_history() -> None:
        """Purge diária do histórico de envios (retenção de 90 dias)."""
        try:
            removed = await prune_alert_logs()
            logger.warning("Purge do histórico: %s linha(s) removida(s)", removed)
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Erro no purge do histórico")

    @staticmethod
    async def _send_alerts(hour: int) -> None:
        """Alertas agendados — sem jitter, igual ao caminho Docker."""
        try:
            await process_scheduled_weather_alerts()
        except Exception:  # pylint: disable=broad-exception-caught
            # `exception` preserva o stack trace: sem ele, um erro de import
            # vira só a mensagem e esconde a causa real.
            logger.exception("Erro no job de alertas (%02dh BRT)", hour)

    @staticmethod
    async def _send_bulletin(period: Period) -> None:
        """Aplica o jitter anti-spam e envia o boletim do período."""
        delay = jitter_delay_seconds(FORECAST_JITTER_SECONDS)
        if delay:
            logger.warning(
                "Boletim %s aguardando jitter anti-spam de %.0fs", period, delay
            )
            await asyncio.sleep(delay)
        try:
            await send_period_forecast(period)
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Erro no boletim %s", period)
