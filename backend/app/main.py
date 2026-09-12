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


app = FastAPI(
    title="Clima-Zap API",
    version="1.0.0",
    description="API de monitoramento e alertas climáticos para o Cariri",
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
app.include_router(webhook_router)


@app.get("/")
def health_check():
    return {"status": "online", "projeto": "Clima-Zap APIEXT III"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/api/v1/clima/ping")
async def ping_clima():
    return {"mensagem": "Módulo de clima pronto para integração com Open-Meteo"}


@app.get("/api/v1/clima/cariri")
async def get_clima_cariri():
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