import time

import httpx

from app.core.config import settings
from app.core.location import LocationData
from app.schemas.schemas import WeatherData

# Cache curto por local. Vale para o processo (Docker) e para o isolate
# (Workers): alertas de 6 em 6 horas e boletim das 06h/14h podem pedir o mesmo
# local na mesma rajada, e /clima repetido no grupo não precisa de novo fetch.
# A Open-Meteo é grátis, então o ganho aqui é latência + subrequests, não cota.
CACHE_TTL_SECONDS = 600.0
_cache: dict[str, tuple[float, WeatherData]] = {}


def _cache_key(location: LocationData | None) -> str:
    """Coordenadas arredondadas (~11 m) — mesmo local, mesma chave."""
    latitude = location["latitude"] if location else settings.default_latitude
    longitude = location["longitude"] if location else settings.default_longitude
    return f"{float(latitude):.4f},{float(longitude):.4f}"


def clear_weather_cache() -> None:
    """Limpa o cache (fixture dos testes; troca de coordenadas padrão)."""
    _cache.clear()


async def fetch_cariri_weather(location: LocationData | None = None) -> WeatherData:
    key = _cache_key(location)
    cached = _cache.get(key)
    if cached is not None and time.monotonic() - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    # Coordenadas configuráveis; o padrão aponta para o bairro Triângulo.
    params = {
        "latitude": location["latitude"] if location else settings.default_latitude,
        "longitude": location["longitude"] if location else settings.default_longitude,
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
        weather = WeatherData(**data)
        _cache[key] = (time.monotonic(), weather)
        return weather
