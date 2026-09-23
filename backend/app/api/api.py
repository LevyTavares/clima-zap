import httpx
from app.core.config import settings
from app.schemas.schemas import WeatherData

async def fetch_cariri_weather() -> WeatherData:
    # Coordenadas aproximadas do Cariri (Barbalha/Juazeiro do Norte)
    params = {
        "latitude": settings.default_latitude,
        "longitude": settings.default_longitude,
        "current": "temperature_2m,relative_humidity_2m,rain,uv_index",
        "daily": "temperature_2m_max,temperature_2m_min",
        "hourly": "temperature_2m,precipitation_probability,relative_humidity_2m,uv_index,weather_code",
        "forecast_days": "2",
        "timezone": "America/Fortaleza"
    }

    # a requisição assíncrona
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(settings.open_meteo_url, params=params)
        response.raise_for_status() # Lança um erro se o status não for 200 OK
        data = response.json()

        # passamos o JSON bruto para o Pydantic validar
        return WeatherData(**data)
