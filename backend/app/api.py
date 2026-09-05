import httpx
from app.schemas import WeatherData

async def fetch_cariri_weather() -> WeatherData:
    url = "https://api.open-meteo.com/v1/forecast"

#coordenadas aproximadas do Cariri(Barbalha/juazeiro do Norte)
    params ={
        latitiude: -7.31,
        longitude: -39.31,
        current_weather: "temperature_2m,relative_humidity_2m,rain,uv_index",
        
    }
    
    # A requisiçao assicrona 
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        response.raise_for_status() # o status não for 200 OK
        data = response.json()
        
        # O JSON bruto para o Pydantic validar
        return WeatherData(**data)