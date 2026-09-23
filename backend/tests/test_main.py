import asyncio

from fastapi.testclient import TestClient

import app.main as main_module
from app.main import (
    FORECAST_JITTER_SECONDS,
    FORECAST_PERIOD_JOBS,
    ALERT_SCHEDULE_HOURS,
    app,
    process_scheduled_weather_alerts,
    scheduler,
    send_period_forecast,
)


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


def test_scheduled_weather_alerts_hours():
    with TestClient(app):
        job = scheduler.get_job("scheduled_weather_alerts")

        assert job is not None
        assert str(job.trigger.fields[5]) == ",".join(map(str, ALERT_SCHEDULE_HOURS))


def test_scheduled_weather_alerts_process(monkeypatch, caplog):
    async def mock_fetch_cariri_weather():
        from app.schemas.schemas import CurrentWeather, WeatherData

        return WeatherData(
            latitude=-7.31,
            longitude=-39.31,
            current=CurrentWeather(
                temperature_2m=28.5,
                relative_humidity_2m=60,
                rain=0,
                uv_index=8,
            ),
        )

    monkeypatch.setattr("app.main.fetch_cariri_weather", mock_fetch_cariri_weather)

    asyncio.run(process_scheduled_weather_alerts())

    assert "Alerta climático programado" in caplog.text


def test_forecast_jobs_registered_when_group_set(monkeypatch):
    monkeypatch.setattr(main_module.settings, "forecast_group_jid", "1203630@g.us")
    # reset scheduler state for isolation
    if scheduler.running:
        scheduler.shutdown(wait=False)
    scheduler.remove_all_jobs()

    main_module.register_forecast_jobs()

    for job_id, hour, period in FORECAST_PERIOD_JOBS:
        job = scheduler.get_job(job_id)
        assert job is not None, f"job {job_id} missing"
        assert job.kwargs == {"period": period}
        trigger = job.trigger
        # CronTrigger fields: year, month, day, week, day_of_week, hour, minute, second
        assert str(trigger.fields[5]) == str(hour)
        assert str(trigger.fields[6]) == "0"
        assert trigger.jitter == FORECAST_JITTER_SECONDS == 900

    scheduler.remove_all_jobs()


def test_forecast_jobs_skipped_without_group(monkeypatch):
    monkeypatch.setattr(main_module.settings, "forecast_group_jid", "")
    if scheduler.running:
        scheduler.shutdown(wait=False)
    scheduler.remove_all_jobs()

    main_module.register_forecast_jobs()

    for job_id, _, _ in FORECAST_PERIOD_JOBS:
        assert scheduler.get_job(job_id) is None


def test_send_period_forecast_skips_when_no_jid(monkeypatch, caplog):
    monkeypatch.setattr(main_module.settings, "forecast_group_jid", "")

    async def boom():
        raise AssertionError("should not fetch")

    monkeypatch.setattr(main_module, "build_period_forecast", boom)

    asyncio.run(send_period_forecast("morning"))
    assert "pulado" in caplog.text


def test_send_period_forecast_sends(monkeypatch):
    monkeypatch.setattr(main_module.settings, "forecast_group_jid", "1203630@g.us")

    async def fake_build(period):
        return f"boletim-{period}"

    sent = {}

    async def fake_send(number, message):
        sent["number"] = number
        sent["message"] = message
        return {"status": "sent"}

    monkeypatch.setattr(main_module, "build_period_forecast", fake_build)
    monkeypatch.setattr(main_module, "send_whatsapp_message", fake_send)

    asyncio.run(send_period_forecast("afternoon"))
    assert sent == {"number": "1203630@g.us", "message": "boletim-afternoon"}


def test_cariri_weather_endpoint(monkeypatch):
    async def mock_fetch_cariri_weather():
        from app.schemas.schemas import CurrentWeather, WeatherData

        return WeatherData(
            latitude=-7.31,
            longitude=-39.31,
            current=CurrentWeather(
                temperature_2m=28.5,
                relative_humidity_2m=60,
                rain=0,
                uv_index=8,
            ),
        )

    monkeypatch.setattr("app.main.fetch_cariri_weather", mock_fetch_cariri_weather)

    response = client.get("/api/v1/clima/cariri")

    assert response.status_code == 200
    data = response.json()
    assert data["weather"]["latitude"] == -7.31
    assert data["weather"]["current"]["temperature_2m"] == 28.5
    assert "alerts" in data
    assert len(data["alerts"]) == 1  # UV igual a 8 aciona 1 alerta
