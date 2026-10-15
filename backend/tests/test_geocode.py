"""Testes do geocoder da Open-Meteo (app.core.geocode) com cliente mockado."""

import asyncio

from app.core.geocode import geocode_city


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeAsyncClient:
    """Mimetica httpx.AsyncClient (contexto assíncrono + get)."""

    payload: dict = {}

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def get(self, url, params=None):
        assert "geocoding-api.open-meteo.com" in url
        assert params["name"]
        return _FakeResponse(self.payload)


def test_geocode_city_returns_name_and_coords(monkeypatch):
    _FakeAsyncClient.payload = {
        "results": [
            {
                "name": "Fortaleza",
                "admin1": "Ceará",
                "latitude": -3.73,
                "longitude": -38.53,
            }
        ]
    }
    monkeypatch.setattr("app.core.geocode.httpx.AsyncClient", _FakeAsyncClient)

    location = asyncio.run(geocode_city("fortaleza"))

    assert location == {
        "name": "Fortaleza, Ceará",
        "latitude": -3.73,
        "longitude": -38.53,
    }


def test_geocode_city_returns_none_when_missing(monkeypatch):
    _FakeAsyncClient.payload = {"results": []}
    monkeypatch.setattr("app.core.geocode.httpx.AsyncClient", _FakeAsyncClient)

    assert asyncio.run(geocode_city("atlantis")) is None


def test_geocode_city_returns_none_on_network_error(monkeypatch):
    class _BrokenClient(_FakeAsyncClient):
        async def get(self, url, params=None):
            raise OSError("rede indisponível")

    monkeypatch.setattr("app.core.geocode.httpx.AsyncClient", _BrokenClient)

    # Falha de rede vira "miss" — o comando responde com as opções em vez de
    # derrubar o background task do webhook.
    assert asyncio.run(geocode_city("crato")) is None
