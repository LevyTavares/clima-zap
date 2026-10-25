import asyncio

from fastapi.testclient import TestClient

import app.main as main_module
from app.core.schedule import MAINTENANCE_HOUR
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


def test_prune_do_historico_agendado_na_hora_de_manutencao():
    # reset scheduler state for isolation
    if scheduler.running:
        scheduler.shutdown(wait=False)
    scheduler.remove_all_jobs()

    main_module.register_maintenance_job()

    job = scheduler.get_job("prune_alert_logs")
    assert job is not None
    assert str(job.trigger.fields[5]) == str(MAINTENANCE_HOUR)
    assert str(job.trigger.fields[6]) == "0"

    scheduler.remove_all_jobs()


def test_scheduled_weather_alerts_process(monkeypatch, caplog):
    async def mock_fetch_cariri_weather(_location=None):
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

    summary = asyncio.run(process_scheduled_weather_alerts())

    assert summary["locations"] >= 1
    assert summary["alerts"] >= 1
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


def test_forecast_jobs_registered_without_main_group(monkeypatch):
    """Grupos inscritos recebem o boletim mesmo sem FORECAST_GROUP_JID."""
    monkeypatch.setattr(main_module.settings, "forecast_group_jid", "")
    if scheduler.running:
        scheduler.shutdown(wait=False)
    scheduler.remove_all_jobs()

    main_module.register_forecast_jobs()

    for job_id, _, _ in FORECAST_PERIOD_JOBS:
        assert scheduler.get_job(job_id) is not None

    scheduler.remove_all_jobs()


def test_send_period_forecast_skips_when_no_target(monkeypatch, caplog):
    monkeypatch.setattr(main_module.settings, "forecast_group_jid", "")

    async def no_groups():
        return []

    async def boom(*args, **kwargs):
        raise AssertionError("should not fetch")

    monkeypatch.setattr(main_module, "list_active_groups", no_groups)
    monkeypatch.setattr(main_module, "build_period_forecast", boom)

    summary = asyncio.run(send_period_forecast("morning"))

    assert summary == {"targets": 0, "sent": 0, "failed": 0}
    assert "pulado" in caplog.text


def test_send_period_forecast_sends(monkeypatch):
    monkeypatch.setattr(main_module.settings, "forecast_group_jid", "1203630@g.us")

    async def no_groups():
        return []

    async def fake_build(period):
        return f"boletim-{period}"

    sent = {}

    async def fake_send(number, message):
        sent["number"] = number
        sent["message"] = message
        return {"status": "sent"}

    monkeypatch.setattr(main_module, "list_active_groups", no_groups)
    monkeypatch.setattr(main_module, "build_period_forecast", fake_build)
    monkeypatch.setattr(main_module, "send_whatsapp_message", fake_send)

    summary = asyncio.run(send_period_forecast("afternoon"))

    assert summary == {"targets": 1, "sent": 1, "failed": 0}
    assert sent == {"number": "1203630@g.us", "message": "boletim-afternoon"}


def test_cariri_weather_endpoint(monkeypatch):
    fetched = {}

    async def mock_fetch_cariri_weather(location=None):
        fetched["location"] = location
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
    assert fetched["location"] is None  # sem ?cidade= → região padrão


def test_cariri_weather_endpoint_with_city(monkeypatch):
    fetched = {}

    async def mock_fetch_cariri_weather(location=None):
        fetched["location"] = location
        from app.schemas.schemas import CurrentWeather, WeatherData

        return WeatherData(
            latitude=location["latitude"],
            longitude=location["longitude"],
            current=CurrentWeather(
                temperature_2m=28.5,
                relative_humidity_2m=60,
                rain=0,
                uv_index=8,
            ),
        )

    monkeypatch.setattr("app.main.fetch_cariri_weather", mock_fetch_cariri_weather)

    response = client.get("/api/v1/clima/cariri", params={"cidade": "Crato"})

    assert response.status_code == 200
    assert fetched["location"]["name"] == "Crato"
    assert response.json()["weather"]["latitude"] == -7.2342


def test_cariri_weather_endpoint_unknown_city():
    response = client.get("/api/v1/clima/cariri", params={"cidade": "Fortaleza"})

    assert response.status_code == 400
    assert "Cidade desconhecida" in response.json()["detail"]
