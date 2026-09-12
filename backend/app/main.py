import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.api.api import fetch_cariri_weather
from app.api.webhook import router as webhook_router
from app.services.alerts import generate_weather_alerts

logger = logging.getLogger(__name__)
ALERT_SCHEDULE_HOURS = [6, 8, 12, 14, 16, 18]
scheduler = AsyncIOScheduler(timezone="America/Fortaleza")


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

# Registra o roteador do webhook modularizado
app.include_router(webhook_router, tags=["Webhook do WhatsApp"])


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
    return {"status": "online", "projeto": "Clima-Zap APIEXT III"}


@app.get(
    "/health", 
    tags=["Health Check"],
    summary="Verificação detalhada de saúde"
)
async def health_check():
    """
    **Health Check:** Ponto de checagem para orquestradores (como o Docker Compose) 
    garantirem que a API não travou em segundo plano.
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
    Consome a API da Open-Meteo em tempo real, processa as métricas 
    atuais e já passa pelo motor de regras de negócio para gerar alertas.
    
    * **Retorna:** Um JSON contendo os dados brutos da previsão e a 
    lista de alertas gerados.
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
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erro ao buscar dados climáticos: {str(e)}"
        )