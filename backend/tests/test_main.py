import asyncio

from fastapi.testclient import TestClient

from app.schemas.schemas import WeatherData
from app.main import ALERT_SCHEDULE_HOURS, app, process_scheduled_weather_alerts, scheduler


client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "status": "online",
        "project": "Clima-Zap",
    }


def test_clima_ping_endpoint():
    response = client.get("/api/v1/clima/ping")

    assert response.status_code == 200
    assert response.json() == {
        "mensagem": "Módulo de clima pronto para integração com Open-Meteo",
    }


def test_scheduled_weather_alerts_hours():
    with TestClient(app):
        job = scheduler.get_job("scheduled_weather_alerts")

        assert job is not None
        assert str(job.trigger.fields[5]) == ",".join(map(str, ALERT_SCHEDULE_HOURS))


def test_scheduled_weather_alerts_process(monkeypatch, caplog):
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

    asyncio.run(process_scheduled_weather_alerts())

    assert "Alerta climático programado" in caplog.text


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
    data = response.json()
    assert data["weather"]["latitude"] == -7.31
    assert data["weather"]["current"]["temperature_2m"] == 28.5
    assert "alerts" in data
    assert len(data["alerts"]) == 1  # UV igual a 8 aciona 1 alerta