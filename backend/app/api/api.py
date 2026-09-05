import httpx
from backend.app.schemas.schemas import WeatherData

async def fetch_cariri_weather() -> WeatherData:
    url = "https://api.open-meteo.com/v1/forecast"
    
    # Coordenadas aproximadas do Cariri (Barbalha/Juazeiro do Norte)
    params = {
        "latitude": -7.31, 
        "longitude": -39.31,
        "current": "temperature_2m,relative_humidity_2m,rain,uv_index",
        "timezone": "America/Fortaleza"
    }
    
    # a requisição assíncrona
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        response.raise_for_status() # Lança um erro se o status não for 200 OK
        data = response.json()
        
        # passamos o JSON bruto para o Pydantic validar
        return WeatherData(**data)