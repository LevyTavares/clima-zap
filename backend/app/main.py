from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Importações com caminhos relativos ao diretório backend/
from app.api.api import fetch_cariri_weather
from app.schemas.schemas import WeatherData

app = FastAPI(
    title="Clima-Zap API",
    version="1.0.0",
    description="API de monitoramento e alertas climáticos para o Cariri"
)

# Configuração de CORS
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

@app.get("/api/v1/clima/cariri", response_model=WeatherData)
async def get_clima_cariri():
    try:
        weather_info = await fetch_cariri_weather()
        return weather_info
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