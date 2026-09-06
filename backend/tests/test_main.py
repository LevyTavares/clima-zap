from fastapi.testclient import TestClient

from app.schemas import WeatherData
from app.services.main import app


client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "status": "online",
        "projeto": "Clima-Zap APIEXT III",
    }


def test_clima_ping_endpoint():
    response = client.get("/api/v1/clima/ping")

    assert response.status_code == 200
    assert response.json() == {
        "mensagem": "Módulo de clima pronto para integração com Open-Meteo",
    }


def test_cariri_weather_endpoint(monkeypatch):
    async def mock_fetch_cariri_weather() -> WeatherData:
        return WeatherData(
            latitude=-7.31,
            longitude=-39.31,
            current={
                "temperature_2m": 28.5,
                "relative_humidity_2m": 60,
                "rain": 0,
                "uv_index": 8,
            },
        )

    monkeypatch.setattr("app.main.fetch_cariri_weather", mock_fetch_cariri_weather)

    response = client.get("/api/v1/clima/cariri")

    assert response.status_code == 200
    assert response.json()["latitude"] == -7.31
    assert response.json()["current"]["temperature_2m"] == 28.5