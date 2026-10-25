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


def match_city(city_query: str | None) -> LocationData | None:
    """
    Retorna as coordenadas da cidade informada (Barbalha, Juazeiro ou Crato)
    ou None se a consulta estiver vazia / não corresponder a nenhuma cidade.
    """
    if not city_query:
        return None

    normalized_query = _normalize_string(city_query)

    for key, data in CRAJUBAR_LOCATIONS.items():
        normalized_key = _normalize_string(key)
        # Verifica se a chave está na busca OU se a busca parcial está na chave
        if normalized_key in normalized_query or normalized_query in normalized_key:
            return data

    return None


def get_location_coords(city_query: str | None) -> LocationData:
    """
    Retorna as coordenadas da cidade informada (Barbalha, Juazeiro ou Crato).
    Caso a cidade não seja informada ou não seja encontrada, retorna Barbalha (fallback).
    """
    return match_city(city_query) or DEFAULT_LOCATION


def parse_coordinates(text: str) -> LocationData | None:
    """Interpreta coordenadas no formato ``lat,lon`` ou ``lat lon``.

    Exemplos aceitos: ``-7.2342,-39.4086`` e ``-7.2342 -39.4086``.
    Usa ponto decimal (vírgula decimal é ambígua com o separador — vira
    rejeição). Retorna None quando o formato ou o intervalo é inválido.
    """
    parts = text.strip().rstrip(",;").replace(",", " ").split()
    if len(parts) != 2:
        return None
    try:
        latitude = float(parts[0])
        longitude = float(parts[1])
    except ValueError:
        return None
    if not -90.0 <= latitude <= 90.0 or not -180.0 <= longitude <= 180.0:
        return None
    return {
        "name": f"{latitude:g}, {longitude:g}",
        "latitude": latitude,
        "longitude": longitude,
    }