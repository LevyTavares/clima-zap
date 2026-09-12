import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.api.api import fetch_cariri_weather
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

@app.get("/")
async def root():
    return {"status": "online", "projeto": "Clima-Zap APIEXT III"}

@app.get("/api/v1/clima/ping")
async def ping_clima():
    return {"mensagem": "Módulo de clima pronto para integração com Open-Meteo"} 

@app.get("/api/v1/clima/cariri")
async def get_clima_cariri():
    try:
        weather_info = await fetch_cariri_weather()
        
        # Extrai os parâmetros para calcular as regras de alerta
        current = weather_info.get("current", {}) if isinstance(weather_info, dict) else weather_info.current.model_dump()
        uv = current.get("uv_index", 0.0)
        humidity = current.get("relative_humidity_2m", 0.0)
        rain = current.get("rain", 0.0)
        
        # Processa as regras de negócio
        alerts = generate_weather_alerts(uv_index=uv, humidity=humidity, rain_prob=rain)
        
        return {
            "weather": weather_info,
            "alerts": alerts
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar dados climáticos: {str(e)}")

# --- WEBHOOK WHATSAPP ---
class WebhookPayload(BaseModel):
    message: str = ""
    sender: str = ""
    to: str = ""

@app.post("/api/v1/webhook", response_model=dict)
async def webhook_message(payload: WebhookPayload):
    """
    Recebe mensagens do webhook do WhatsApp.

    SEGURANÇA: Em produção, implementar verificação da assinatura do webhook (por exemplo, X-Hub-Signature da API do WhatsApp/Evolution) para evitar solicitações falsas (spoofing). Utilize validação de secret token antes de processar o payload.
    """
    command = payload.message.lower().strip()
    response = route_command(command, payload.sender)
    return {"status": "ok", "reply": response}

def route_command(command: str, sender: str) -> str:
    if command in ("help", "?", "comandos"):
        return ("help_text")
    if command in ("status", "status?"):
        return ("system_online")
    if command.startswith("forecast"):
        return ("forecast_ready")
    return ("comando_nao_entendido")