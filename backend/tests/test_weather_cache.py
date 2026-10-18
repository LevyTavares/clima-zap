"""Testes do cache curto do Open-Meteo (``app.api.api``).

O cache é do processo/isolate e existe para não repetir o fetch quando os
alertas e o boletim caem na mesma rajada (06h/14h BRT) ou quando o grupo pede
``/clima`` duas vezes seguidas.
"""

import asyncio

import app.api.api as weather_api
from app.api.api import fetch_cariri_weather
from app.core.config import settings

PAYLOAD = {
    "latitude": -7.31,
    "longitude": -39.31,
    "current": {
        "temperature_2m": 28.5,
        "relative_humidity_2m": 60,
        "rain": 0,
        "uv_index": 8,
    },
}


class _FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return PAYLOAD


class _FakeAsyncClient:
    """Mimetica httpx.AsyncClient e conta quantos fetches aconteceram."""

    calls = 0

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def get(self, _url, params=None):
        assert params["timezone"] == "America/Fortaleza"
        _FakeAsyncClient.calls += 1
        return _FakeResponse()


def _fake_client(monkeypatch) -> None:
    _FakeAsyncClient.calls = 0
    monkeypatch.setattr(weather_api.httpx, "AsyncClient", _FakeAsyncClient)


def test_segundo_fetch_do_mesmo_local_vem_do_cache(monkeypatch):
    _fake_client(monkeypatch)

    first = asyncio.run(fetch_cariri_weather())
    second = asyncio.run(fetch_cariri_weather())

    assert _FakeAsyncClient.calls == 1
    assert first is second


def test_local_diferente_nao_reaproveita_o_cache(monkeypatch):
    _fake_client(monkeypatch)
    crato = {"name": "Crato", "latitude": -7.2342, "longitude": -39.4086}

    asyncio.run(fetch_cariri_weather())
    asyncio.run(fetch_cariri_weather(crato))
    asyncio.run(fetch_cariri_weather(crato))

    assert _FakeAsyncClient.calls == 2


def test_cache_expira_e_refaz_o_fetch(monkeypatch):
    _fake_client(monkeypatch)
    monkeypatch.setattr(weather_api, "CACHE_TTL_SECONDS", 0.0)

    asyncio.run(fetch_cariri_weather())
    asyncio.run(fetch_cariri_weather())

    assert _FakeAsyncClient.calls == 2


def test_coordenadas_padrao_vem_das_settings(monkeypatch):
    monkeypatch.setattr(settings, "default_latitude", -7.31)
    monkeypatch.setattr(settings, "default_longitude", -39.31)

    assert weather_api._cache_key(None) == "-7.3100,-39.3100"  # pylint: disable=protected-access
