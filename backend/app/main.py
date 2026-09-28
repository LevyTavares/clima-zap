import logging
from pathlib import Path
from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from evolution_api import EvolutionError
from sqlalchemy.exc import SQLAlchemyError

from app.api.api import fetch_cariri_weather
from app.api.webhook import router as webhook_router
from app.api.subscription import router as subscription_router
from app.core.config import ROOT_DIR, settings
from app.services.alerts import generate_weather_alerts
from app.services.alert_history import record_alert_dispatch
from app.services.evolution_client import send_whatsapp_message
from app.services.forecast import Period, build_period_forecast
from app.services.weather_dispatch import dispatch_weather_alerts

# Prefer DOCS_DIR (.env / Docker mount at /docs); fallback to repo docs/ (dev).
DOCS_DIR = Path(settings.docs_dir) if settings.docs_dir else ROOT_DIR / "docs"

logger = logging.getLogger(__name__)
ALERT_SCHEDULE_HOURS = [6, 8, 12, 14, 16, 18]
scheduler = AsyncIOScheduler(timezone="America/Fortaleza")

# Boletim periódico: manhã / tarde / noite — jitter 0–15min anti-spam
FORECAST_PERIOD_JOBS: list[tuple[str, int, Period]] = [
    ("forecast_morning", 6, "morning"),
    ("forecast_afternoon", 14, "afternoon"),
    ("forecast_night", 20, "night"),
]
FORECAST_JITTER_SECONDS = 900  # 15min


async def process_scheduled_weather_alerts() -> None:
    weather_info = await fetch_cariri_weather()
    current = weather_info.current.model_dump()
    alerts = generate_weather_alerts(
        uv_index=current.get("uv_index", 0.0),
        humidity=current.get("relative_humidity_2m", 0.0),
        rain_prob=current.get("rain", 0.0),
    )

    for alert in alerts:
        logger.warning("Alerta climático programado: %s", alert)
    await dispatch_weather_alerts(alerts)


async def send_period_forecast(period: Period) -> None:
    """Busca boletim do período e envia para FORECAST_GROUP_JID."""
    log = logging.getLogger("uvicorn.error")
    group_jid = settings.forecast_group_jid
    if not group_jid:
        log.warning("FORECAST_GROUP_JID vazio — forecast %s pulado", period)
        return
    try:
        message = await build_period_forecast(period)
    except (httpx.HTTPError, ValueError) as e:
        log.error("Erro ao montar forecast %s: %s", period, e)
        return
    try:
        result = await send_whatsapp_message(group_jid, message)
        log.warning("Forecast %s enviado para %s: %s", period, group_jid, result)
    except EvolutionError as e:
        log.error("Erro ao enviar forecast %s para %s: %s", period, group_jid, e)
        try:
            await record_alert_dispatch(f"forecast_{period}", group_jid, "failed")
        except SQLAlchemyError as log_error:
            log.error("Erro ao registrar envio do forecast %s: %s", period, log_error)
        return

    delivery_status = result.get("status", "sent") if isinstance(result, dict) else "sent"
    try:
        await record_alert_dispatch(f"forecast_{period}", group_jid, str(delivery_status))
    except SQLAlchemyError as log_error:
        log.error("Erro ao registrar envio do forecast %s: %s", period, log_error)


def register_forecast_jobs() -> None:
    """Registra os 3 jobs de boletim — só se grupo configurado."""
    log = logging.getLogger("uvicorn.error")
    if not settings.forecast_group_jid:
        log.warning("FORECAST_GROUP_JID vazio — jobs de forecast periódico não registrados")
        return
    for job_id, hour, period in FORECAST_PERIOD_JOBS:
        scheduler.add_job(
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
        settings.forecast_group_jid,
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    scheduler.add_job(
        process_scheduled_weather_alerts,
        trigger="cron",
        hour=",".join(map(str, ALERT_SCHEDULE_HOURS)),
        minute=0,
        id="scheduled_weather_alerts",
        replace_existing=True,
    )
    register_forecast_jobs()
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown()


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
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registra os roteadores modularizados
app.include_router(webhook_router, tags=["Webhook do WhatsApp"])
app.include_router(subscription_router, tags=["Gestão de Inscrições"])


# --- 2. DOCUMENTAÇÃO DAS ROTAS ---
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
    summary="Verificação detalhada de saúde"
)
async def health_check():
    """
    **Health Check:** Ponto de checagem para orquestradores (como o Docker Compose).
    """
    return {"status": "healthy"}


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
async def get_clima_cariri():
    """
    Consome a API da Open-Meteo em tempo real e gera alertas baseados nas regras de negócio.
    """
    try:
        weather_info = await fetch_cariri_weather()
        current = (
            weather_info.get("current", {})
            if isinstance(weather_info, dict)
            else weather_info.current.model_dump()
        )
        uv = current.get("uv_index", 0.0)
        humidity = current.get("relative_humidity_2m", 0.0)
        rain = current.get("rain", 0.0)

        alerts = generate_weather_alerts(uv_index=uv, humidity=humidity, rain_prob=rain)

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
async def whatsapp_docs():
    docs_file = DOCS_DIR / "whatsapp-integration.md"
    if not docs_file.exists():
        raise HTTPException(status_code=404, detail="Documentação não encontrada")
    return {"content": docs_file.read_text(encoding="utf-8")}


@app.get(
    "/docs/docker",
    tags=["Documentação"],
    summary="Documentação do setup Docker Compose"
)
async def docker_docs():
    docs_file = DOCS_DIR / "docker-setup.md"
    if not docs_file.exists():
        raise HTTPException(status_code=404, detail="Documentação não encontrada")
    return {"content": docs_file.read_text(encoding="utf-8")}