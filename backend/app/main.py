from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

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