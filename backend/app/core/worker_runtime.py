"""Ponte com o runtime Cloudflare Workers (Python Workers / Pyodide).

O Worker (`backend/worker.py`) entrega o `env` do Cloudflare (bindings D1,
vars e secrets) que precisamos expor para o restante da aplicação:

- ``is_workers_runtime()``: detecta Pyodide (workerd) sem importar nada do
  ecossistema Cloudflare — seguro em imports no topo de módulos.
- ``attach(env)``: registra o env e copia vars/secrets para ``settings``.
- ``on_workers()``: True após ``attach`` — é o interruptor usado por
  persistence/alert_history para escolher D1 em vez de SQLAlchemy.
- ``d1()``: binding do banco D1 (``env.DB``) ou None.
- ``brt_hour(ms)``: hora de Fortaleza (UTC-3 fixo, sem DST desde 2019) a
  partir do ``scheduledTime`` (epoch ms) de um Cron Trigger.

No caminho Docker (CPython) nada disso é ativado: o APScheduler e o
SQLAlchemy continuam responsáveis pelos agendamentos e pela persistência.
"""

import logging
import os
import sys
from datetime import datetime, timezone

from pydantic import SecretStr

from app.core.config import settings

# Estado do isolate: env do Workers (binding) quando presente.
_STATE: dict[str, object] = {}

logger = logging.getLogger(__name__)

# Chaves de Settings sincronizadas a partir das vars/secrets do Worker.
# Nomes iguais aos env vars usados no caminho Docker (.env).
SYNCED_KEYS = (
    "port",
    "environment",
    "default_city",
    "default_latitude",
    "default_longitude",
    "open_meteo_url",
    "evolution_api_url",
    "evolution_api_key",
    "evolution_instance_name",
    "target_phone_number",
    "bot_name",
    "forecast_group_jid",
    "webhook_auth_token",
    "docs_dir",
    "database_url",
    "database_ssl",
    "cors_origins",
)

# America/Fortaleza = UTC-3 o ano todo (DST extinto no Brasil desde 2019).
BRT_UTC_OFFSET_HOURS = -3


def is_workers_runtime() -> bool:
    """True quando executando dentro do workerd (Pyodide)."""
    return sys.platform == "emscripten"


def attach(env: object) -> None:
    """Registra o env do Worker e sincroniza vars/secrets em ``settings``.

    Idempotente: chamado no middleware de cada request e no handler
    ``scheduled``. No caminho local ``env`` vem None e nada muda.
    """
    if env is None or _STATE.get("env") is env:
        return
    _STATE["env"] = env
    for key in SYNCED_KEYS:
        # Wrangler convention: vars/secrets em CAIXA ALTA (EVOLUTION_API_KEY);
        # aceitamos também o nome em snake_case igual ao env var do Docker.
        value = getattr(env, key.upper(), None)
        if value is None:
            value = getattr(env, key, None)
        if value is None:
            continue
        text = str(value)
        if key == "database_url":
            settings.database_url = SecretStr(text)
        elif key == "database_ssl":
            settings.database_ssl = text.strip().lower() in ("1", "true", "yes")
        elif key == "port":
            try:
                settings.port = int(text)
            except ValueError:
                continue
        else:
            setattr(settings, key, text)
        os.environ[key] = text
    for warning in settings.production_warnings():
        logger.warning("Config insegura em produção: %s", warning)


def on_workers() -> bool:
    """True quando o env do Worker já foi anexado (caminho D1 ativo)."""
    return _STATE.get("env") is not None


def d1() -> object | None:
    """Binding do banco D1 (``env.DB``) ou None se não houver."""
    env = _STATE.get("env")
    return getattr(env, "DB", None) if env is not None else None


def assets() -> object | None:
    """Binding de Assets (``env.ASSETS``) ou None se não houver."""
    env = _STATE.get("env")
    return getattr(env, "ASSETS", None) if env is not None else None


def brt_hour(scheduled_time_ms: int) -> int:
    """Converte o ``scheduledTime`` (epoch ms, UTC) em hora BRT (0-23)."""
    moment = datetime.fromtimestamp(scheduled_time_ms / 1000, tz=timezone.utc)
    return (moment.hour + BRT_UTC_OFFSET_HOURS) % 24


def reset_for_tests() -> None:
    """Limpa o estado do isolate (uso exclusivo dos testes)."""
    _STATE.clear()
