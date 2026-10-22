import logging
from pathlib import Path
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING
import httpx
from fastapi import FastAPI, HTTPException, Depends, Request
from evolution_api import EvolutionError

from app.api.api import fetch_cariri_weather
from app.api.forecast import router as forecast_router
from app.api.webhook import router as webhook_router
from app.api.subscription import router as subscription_router
from app.core import worker_runtime
from app.core.config import ROOT_DIR, settings
from app.core.cors import SettingsCORSMiddleware
from app.core.location import CRAJUBAR_LOCATIONS, LocationData, match_city
from app.core.schedule import (
    ALERT_SCHEDULE_HOURS,
    FORECAST_JITTER_SECONDS,
    FORECAST_PERIOD_JOBS,
    MAINTENANCE_HOUR,
)
from app.db import d1
from app.db.errors import storage_errors
from app.db.session import get_db
from app.services.alerts import generate_weather_alerts
from app.services.alert_history import prune_alert_logs, record_alert_dispatch
from app.services.evolution_client import send_whatsapp_message
from app.services.forecast import Period, build_period_forecast
from app.services.persistence import (
    group_active_subscribers_by_city,
    list_active_groups,
    resolve_group_location,
    subscriber_location,
)
from app.services.weather_dispatch import dispatch_weather_alerts

if TYPE_CHECKING:  # anotação apenas: apscheduler não entra no bundle do Worker
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Prefer DOCS_DIR (.env / Docker mount at /docs); fallback to repo docs/ (dev).
DOCS_DIR = Path(settings.docs_dir) if settings.docs_dir else ROOT_DIR / "docs"

logger = logging.getLogger(__name__)
# Horas, jitter dos jobs e expressões de cron vivem em `app.core.schedule` —
# fonte única compartilhada com os Cron Triggers do Workers (backend/worker.py).
#
# `scheduler` só existe no caminho Docker: no Workers os agendamentos são Cron
# Triggers e o bundle não empacota APScheduler/tzdata (ver backend/pyproject.toml).
scheduler: "AsyncIOScheduler | None" = None
if not worker_runtime.is_workers_runtime():
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler(timezone="America/Fortaleza")


async def process_scheduled_weather_alerts() -> None:
    """Gera e envia alertas por região: sempre a padrão + cada cidade de assinantes."""
    try:
        groups = await group_active_subscribers_by_city()
    except storage_errors() as error:
        logger.error("Erro ao buscar assinantes ativos: %s", error)
        groups = {}

    # Região padrão ('') é sempre avaliada, mesmo sem assinantes, para logar alertas.
    for city, subscribers in {"": [], **groups}.items():
        location = resolve_group_location(city, subscribers)
        weather_info = await fetch_cariri_weather(location)
        current = weather_info.current.model_dump()
        alerts = generate_weather_alerts(
            uv_index=current.get("uv_index", 0.0),
            humidity=current.get("relative_humidity_2m", 0.0),
            rain_prob=current.get("rain", 0.0),
        )

        for alert in alerts:
            logger.warning("Alerta climático programado: %s", alert)
        await dispatch_weather_alerts(alerts, subscribers=subscribers)


async def _bulletin_targets() -> list[tuple[str, LocationData | None]]:
    """Destinos do boletim: grupo principal + grupos inscritos (sem duplicar).

    O formato ``(JID, local)`` carrega o local junto porque cada grupo recebe o
    boletim da sua própria cidade; ``local`` None = região padrão da aplicação.
    """
    log = logging.getLogger("uvicorn.error")
    group_jid = settings.forecast_group_jid
    try:
        groups = await list_active_groups()
    except storage_errors() as error:
        log.error("Erro ao buscar grupos inscritos: %s", error)
        groups = []

    by_phone = {subscriber.phone: subscriber for subscriber in groups}
    targets: list[tuple[str, LocationData | None]] = []
    if group_jid:
        targets.append((group_jid, subscriber_location(by_phone.get(group_jid))))
    for subscriber in groups:
        if subscriber.phone != group_jid:
            targets.append((subscriber.phone, subscriber_location(subscriber)))
    return targets


async def _record_forecast_dispatch(
    period: Period, recipient: str, status: str
) -> None:
    """Registra o envio no histórico (falha de storage não interrompe o job)."""
    try:
        await record_alert_dispatch(f"forecast_{period}", recipient, status)
    except storage_errors() as log_error:
        logging.getLogger("uvicorn.error").error(
            "Erro ao registrar envio do forecast %s: %s", period, log_error
        )


async def send_period_forecast(period: Period) -> None:
    """Envia o boletim do período ao grupo principal e aos grupos inscritos.

    Grupos com o mesmo local compartilham a mesma mensagem (um fetch só);
    grupos sem local cadastrado recebem o boletim da região padrão.
    """
    log = logging.getLogger("uvicorn.error")
    targets = await _bulletin_targets()
    if not targets:
        log.warning(
            "FORECAST_GROUP_JID vazio e nenhum grupo inscrito — "
            "forecast %s pulado",
            period,
        )
        return

    messages: dict[tuple[float, float] | None, str] = {}
    for recipient, location in targets:
        key = (location["latitude"], location["longitude"]) if location else None
        if key not in messages:
            try:
                messages[key] = (
                    await build_period_forecast(period)
                    if location is None
                    else await build_period_forecast(period, location=location)
                )
            except (httpx.HTTPError, ValueError) as e:
                log.error(
                    "Erro ao montar forecast %s para %s: %s", period, recipient, e
                )
                continue

        try:
            result = await send_whatsapp_message(recipient, messages[key])
            log.warning("Forecast %s enviado para %s: %s", period, recipient, result)
        except EvolutionError as e:
            log.error("Erro ao enviar forecast %s para %s: %s", period, recipient, e)
            await _record_forecast_dispatch(period, recipient, "failed")
            continue

        delivery_status = (
            result.get("status", "sent") if isinstance(result, dict) else "sent"
        )
        await _record_forecast_dispatch(period, recipient, str(delivery_status))


def register_maintenance_job() -> None:
    """Registra o prune diário do histórico (alert_logs) — só no Docker.

    No Workers ele roda pelo Cron Trigger das 20h BRT (``backend/worker.py``).
    """
    active_scheduler = scheduler
    if active_scheduler is None:
        return
    active_scheduler.add_job(
        prune_alert_logs,
        trigger="cron",
        hour=MAINTENANCE_HOUR,
        minute=0,
        id="prune_alert_logs",
        replace_existing=True,
    )


def register_forecast_jobs() -> None:
    """Registra os 3 jobs de boletim (grupo principal + grupos inscritos)."""
    log = logging.getLogger("uvicorn.error")
    active_scheduler = scheduler
    if active_scheduler is None:  # Workers: agendamentos vêm dos Cron Triggers
        return
    for job_id, hour, period in FORECAST_PERIOD_JOBS:
        active_scheduler.add_job(
            send_period_forecast,
            trigger="cron",
            hour=hour,
            minute=0,
            jitter=FORECAST_JITTER_SECONDS,
            kwargs={"period": period},
            id=job_id,
            replace_existing=True,
        )
    log.warning(
        "Forecast periódico ativo: 3 jobs (06/14/20h ±15min) → %s",
        settings.forecast_group_jid or "somente grupos inscritos",
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    active_scheduler = scheduler
    if worker_runtime.is_workers_runtime() or active_scheduler is None:
        # No Workers os agendamentos vêm dos Cron Triggers (backend/worker.py)
        # e o ASGI serveria o lifespan a cada request — não iniciamos o
        # APScheduler aqui.
        yield
        return
    for warning in settings.production_warnings():
        logger.warning("Config insegura em produção: %s", warning)
    active_scheduler.add_job(
        process_scheduled_weather_alerts,
        trigger="cron",
        hour=",".join(map(str, ALERT_SCHEDULE_HOURS)),
        minute=0,
        id="scheduled_weather_alerts",
        replace_existing=True,
    )
    # Retenção do histórico: um prune por dia, na hora do boletim da noite.
    register_maintenance_job()
    register_forecast_jobs()
    active_scheduler.start()
    try:
        yield
    finally:
        active_scheduler.shutdown()


# --- 1. METADADOS DO SWAGGER UI ---
app = FastAPI(
    title="🌤️ Clima-Zap API",
    version="1.0.0",
    description=(
        "API de monitoramento e alertas climáticos para o Cariri. "
        "Focada em integração e automação via WhatsApp."
    ),
    contact={"name": "Equipe Clima-Zap"},
    lifespan=lifespan,
)

app.add_middleware(
    # Origens vêm de CORS_ORIGINS (lidas por request); sem curinga e sem
    # credenciais — a API não usa cookies.
    SettingsCORSMiddleware,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def attach_worker_env(request: Request, call_next):
    """Cloudflare Workers: expõe bindings/vars (env) para settings e D1.

    No caminho local ``scope['env']`` não existe e nada muda.
    """
    worker_runtime.attach(request.scope.get("env"))
    return await call_next(request)


# Registra os roteadores modularizados
app.include_router(webhook_router, tags=["Webhook do WhatsApp"])
app.include_router(subscription_router, tags=["Gestão de Inscrições"])
app.include_router(forecast_router)


# --- 2. DOCUMENTAÇÃO DAS ROTAS ---
async def _read_docs_file(request: Request, filename: str) -> str:
    """Lê um markdown de docs: Assets do Worker (Workers) ou disco (local)."""
    assets = worker_runtime.assets()
    if assets is not None:
        # O fetch do binding exige URL absoluta (a origem do request).
        response = await assets.fetch(f"{request.base_url}{filename}")
        if response.status == 200:
            return str(await response.text())
    docs_file = DOCS_DIR / filename
    if not docs_file.exists():
        raise HTTPException(status_code=404, detail="Documentação não encontrada")
    return docs_file.read_text(encoding="utf-8")


@app.get(
    "/", 
    tags=["Health Check"],
    summary="Verifica o status raiz da API"
)
def root():
    """
    **Rota Raiz:** Confirma se o servidor principal está online.
    """
    return {"status": "online", "project": "Clima-Zap"}


@app.get(
    "/health", 
    tags=["Health Check"],
    summary="Verificação detalhada de saúde dos serviços (Task #35)"
)
async def health_check(db=Depends(get_db)):
    """
    **Health Check Expandido:** Avalia a integridade do banco de dados relacional 
    e a conectividade com os serviços externos de clima.
    """
    health_status = {
        "status": "healthy",
        "services": {
            "database": "unhealthy",
            "open_meteo_api": "unhealthy"
        }
    }

    # 1. Validação de Conectividade com o Banco de Dados
    # No Workers (D1) o check usa o binding direto; local, o SQLAlchemy.
    try:
        if worker_runtime.on_workers():
            await d1.ping()
        else:
            from app.db.orm import text  # pylint: disable=import-outside-toplevel

            await db.execute(text("SELECT 1"))
        health_status["services"]["database"] = "healthy"
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Falha no health check do banco de dados: %s", e)
        health_status["status"] = "degraded"

    # 2. Validação da API Externa de Clima (Open-Meteo)
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.open-meteo.com/v1/forecast?latitude=-7.31&longitude=-39.31&current=temperature_2m",
                timeout=5.0
            )
            if response.status_code == 200:
                health_status["services"]["open_meteo_api"] = "healthy"
            else:
                health_status["status"] = "degraded"
    except httpx.HTTPError as e:
        logger.error("Falha no health check da Open-Meteo: %s", e)
        health_status["status"] = "degraded"

    return health_status


@app.get(
    "/api/v1/clima/ping", 
    tags=["Health Check"],
    summary="Ping dos serviços de clima"
)
async def ping_clima():
    """
    Confirma se o submódulo de clima e formatação está pronto para operar.
    """
    return {"mensagem": "Módulo de clima pronto para integração com Open-Meteo"}


@app.get(
    "/api/v1/clima/cariri", 
    tags=["Dados Climáticos"],
    summary="Busca a previsão atual e alertas da região"
)
async def get_clima_cariri(cidade: str | None = None):
    """
    Consome a API da Open-Meteo em tempo real e gera alertas baseados nas regras de negócio.

    Use `?cidade=` para uma localização do Crajubar (Barbalha, Juazeiro do Norte, Crato);
    sem parâmetro usa a região padrão.
    """
    location = None
    query = cidade.strip() if cidade else None
    if query:
        location = match_city(query)
        if location is None:
            options = ", ".join(data["name"] for data in CRAJUBAR_LOCATIONS.values())
            raise HTTPException(
                status_code=400,
                detail=f"Cidade desconhecida: {query}. Opções: {options}.",
            )
    try:
        weather_info = await fetch_cariri_weather(location)
        current = weather_info.current.model_dump()
        alerts = generate_weather_alerts(
            uv_index=current.get("uv_index", 0.0),
            humidity=current.get("relative_humidity_2m", 0.0),
            rain_prob=current.get("rain", 0.0),
        )

        return {"weather": weather_info, "alerts": alerts}
    except (httpx.HTTPError, ValueError) as e:
        raise HTTPException(
            status_code=500, detail=f"Erro ao buscar dados climáticos: {str(e)}"
        ) from e


@app.get(
    "/docs/whatsapp",
    tags=["Documentação"],
    summary="Documentação da integração WhatsApp"
)
async def whatsapp_docs(request: Request):
    return {"content": await _read_docs_file(request, "whatsapp-integration.md")}


@app.get(
    "/docs/docker",
    tags=["Documentação"],
    summary="Documentação do setup Docker Compose"
)
async def docker_docs(request: Request):
    return {"content": await _read_docs_file(request, "docker-setup.md")}
