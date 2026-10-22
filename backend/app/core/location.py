# pylint: disable=duplicate-code
import unicodedata
from typing import Dict, TypedDict


class LocationData(TypedDict):
    name: str
    state: str
    latitude: float
    longitude: float


CRAJUBAR_LOCATIONS: Dict[str, LocationData] = {
    "juazeiro do norte": {
        "name": "Juazeiro do Norte",
        "state": "CE",
        "latitude": -7.2142,
        "longitude": -39.3153,
    },
    "barbalha": {
        "name": "Barbalha",
        "state": "CE",
        "latitude": -7.3108,
        "longitude": -39.3018,
    },
    "crato": {
        "name": "Crato",
        "state": "CE",
        "latitude": -7.2342,
        "longitude": -39.4086,
    },
    "juazeiro": {
        "name": "Juazeiro do Norte",
        "state": "CE",
        "latitude": -7.2142,
        "longitude": -39.3153,
    },
    "juazeiro ba": {
        "name": "Juazeiro",
        "state": "BA",
        "latitude": -9.4116,
        "longitude": -40.5033,
    },
    "juazeiro da bahia": {
        "name": "Juazeiro",
        "state": "BA",
        "latitude": -9.4116,
        "longitude": -40.5033,
    },
}

DEFAULT_LOCATION = CRAJUBAR_LOCATIONS["barbalha"]


def _normalize_string(text: str) -> str:
    text = text.lower().strip()
    nfkd_form = unicodedata.normalize("NFKD", text)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])


def get_location_coords(city_query: str | None) -> LocationData:
    if not city_query:
        return DEFAULT_LOCATION

    query_norm = _normalize_string(city_query)

    if query_norm in CRAJUBAR_LOCATIONS:
        return CRAJUBAR_LOCATIONS[query_norm]

    sorted_keys = sorted(CRAJUBAR_LOCATIONS.keys(), key=len, reverse=True)

    for key in sorted_keys:
        key_norm = _normalize_string(key)
        if key_norm in query_norm or query_norm in key_norm:
            return CRAJUBAR_LOCATIONS[key]

    return DEFAULT_LOCATION


def match_city(city_query: str | None) -> LocationData:
    """Alias de compatibilidade para o webhook."""
    return get_location_coords(city_query)


def parse_coordinates(text: str | None) -> tuple[float, float] | None:
    """Extrai latitude e longitude de strings no formato 'lat, lon'."""
    if not text:
        return None
    try:
        parts = [p.strip() for p in text.split(",")]
        if len(parts) == 2:
            lat, lon = float(parts[0]), float(parts[1])
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return lat, lon
    except ValueError:
        pass
    return None
