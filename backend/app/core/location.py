import unicodedata
from typing import Dict, TypedDict


class LocationData(TypedDict):
    name: str
    latitude: float
    longitude: float


CRAJUBAR_LOCATIONS: Dict[str, LocationData] = {
    "barbalha": {
        "name": "Barbalha",
        "latitude": -7.3108,
        "longitude": -39.3018,
    },
    "juazeiro do norte": {
        "name": "Juazeiro do Norte",
        "latitude": -7.2142,
        "longitude": -39.3153,
    },
    "crato": {
        "name": "Crato",
        "latitude": -7.2342,
        "longitude": -39.4086,
    },
}

DEFAULT_LOCATION = CRAJUBAR_LOCATIONS["barbalha"]


def _normalize_string(text: str) -> str:
    """Remove acentos e converte para minúsculas para busca flexível."""
    text = text.lower().strip()
    nfkd_form = unicodedata.normalize("NFKD", text)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])


def get_location_coords(city_query: str | None) -> LocationData:
    """
    Retorna as coordenadas da cidade informada (Barbalha, Juazeiro ou Crato).
    Caso a cidade não seja informada ou não seja encontrada, retorna Barbalha (fallback).
    """
    if not city_query:
        return DEFAULT_LOCATION

    normalized_query = _normalize_string(city_query)

    for key, data in CRAJUBAR_LOCATIONS.items():
        normalized_key = _normalize_string(key)
        # Verifica se a chave está na busca OU se a busca parcial está na chave
        if normalized_key in normalized_query or normalized_query in normalized_key:
            return data

    return DEFAULT_LOCATION