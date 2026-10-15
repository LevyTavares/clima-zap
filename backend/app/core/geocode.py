"""Geocodificação de cidades fora dos presets do Crajubar.

Usa o geocoder aberto da própria Open-Meteo (mesma família da API de previsão,
sem API key). Alimenta o comando ``/configuracao <cidade>`` para qualquer
cidade do mundo quando ela não casa com ``match_city``.
"""

import httpx

from app.core.location import LocationData

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"


async def geocode_city(query: str) -> LocationData | None:
    """Resolve o nome de uma cidade em coordenadas; None se não encontrar."""
    params = {"name": query, "count": 1, "language": "pt", "format": "json"}
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(GEOCODING_URL, params=params)
            response.raise_for_status()
            results = response.json().get("results") or []
    except (httpx.HTTPError, ValueError, OSError):
        return None
    if not results:
        return None

    first = results[0]
    latitude = first.get("latitude")
    longitude = first.get("longitude")
    if latitude is None or longitude is None:
        return None
    # "Juazeiro do Norte, Ceará" — nome + região administrativa quando houver.
    name = ", ".join(
        str(part) for part in (first.get("name"), first.get("admin1")) if part
    )
    return {
        "name": name or query,
        "latitude": float(latitude),
        "longitude": float(longitude),
    }
