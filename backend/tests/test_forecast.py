from datetime import datetime, timedelta

import asyncio

from app.formatter import format_period_summary, get_period_greeting, weather_code_to_text
from app.schemas.schemas import CurrentWeather, DailyWeather, HourlyWeather, WeatherData
from app.services.forecast import (
    PERIOD_HOURS,
    aggregate_period_hourly,
    build_current_forecast,
    build_period_forecast,
)


def _hourly_fixture() -> HourlyWeather:
    # 2 dias de horas (0..47) — 2026-09-23 e 2026-09-24
    times = []
    temps = []
    pops = []
    hums = []
    uvs = []
    codes = []
    base = datetime(2026, 9, 23, 0, 0)

    for h in range(48):
        dt = base + timedelta(hours=h)
        times.append(dt.isoformat())
        temps.append(20.0 + h % 15)
        pops.append(float((h * 7) % 100))
        hums.append(40.0 + h % 40)
        uvs.append(0.0 if dt.hour < 6 or dt.hour > 18 else 9.0)
        codes.append(1 if h % 3 else 61)
    return HourlyWeather(
        time=times,
        temperature_2m=temps,
        precipitation_probability=pops,
        relative_humidity_2m=hums,
        uv_index=uvs,
        weather_code=codes,
    )


def test_period_hours_defined():
    assert set(PERIOD_HOURS) == {"morning", "afternoon", "night"}
    assert PERIOD_HOURS["morning"] == (6, 12)
    assert PERIOD_HOURS["night"] == (18, 6)


def test_aggregate_morning_window():
    now = datetime(2026, 9, 23, 6, 30)
    agg = aggregate_period_hourly(_hourly_fixture(), "morning", now=now)
    assert agg is not None
    # janela 06..11 → índices 6..11 → temps 26..31
    assert agg["temp_min"] == 26.0
    assert agg["temp_max"] == 31.0
    assert len(agg["weather_codes"]) == 6
    assert 0 <= agg["rain_prob_max"] <= 100


def test_aggregate_night_crosses_midnight():
    now = datetime(2026, 9, 23, 20, 0)
    agg = aggregate_period_hourly(_hourly_fixture(), "night", now=now)
    assert agg is not None
    # 18h..23h dia 23 + 0h..5h dia 24 → 12 pontos
    assert len(agg["weather_codes"]) == 12


def test_aggregate_afternoon():
    now = datetime(2026, 9, 23, 14, 0)
    agg = aggregate_period_hourly(_hourly_fixture(), "afternoon", now=now)
    assert agg is not None
    # 12..17 → 6 pontos
    assert len(agg["weather_codes"]) == 6


def test_format_period_summary_contains_fields():
    msg = format_period_summary(
        city="Juazeiro do Norte",
        period="morning",
        temp_min=21,
        temp_max=32,
        humidity_avg=55,
        rain_prob_max=80,
        uv_max=9.0,
        weather_codes=[61, 61, 1],
    )
    assert "Manhã" in msg
    assert "Juazeiro do Norte" in msg
    assert "21°C" in msg and "32°C" in msg
    assert "55%" in msg
    assert "80%" in msg
    # chuva 80 → dica guarda-chuva
    assert "guarda-chuva" in msg


def test_period_greeting_and_weather_code():
    g = get_period_greeting("night")
    assert g in [
        "Boa noite, pessoal! 🌙",
        "Resumo da noite e madrugada 🌌",
        "Boa noite! Previsão pra agora e amanhã de manhã 🌠",
        "Antes de dormir, o clima da noite 🦉",
    ]
    assert weather_code_to_text(61) == "Chuva fraca"
    assert weather_code_to_text(999) == "Código 999"


def test_build_period_forecast_uses_hourly(monkeypatch):
    async def mock_fetch():
        return WeatherData(
            latitude=-7.31,
            longitude=-39.31,
            current=CurrentWeather(
                temperature_2m=28.0,
                relative_humidity_2m=50,
                rain=0,
                uv_index=5,
            ),
            hourly=_hourly_fixture(),
        )

    monkeypatch.setattr("app.services.forecast.fetch_cariri_weather", mock_fetch)
    now = datetime(2026, 9, 23, 7, 0)
    msg = asyncio.run(build_period_forecast("morning", now=now))
    assert "Manhã" in msg
    assert "Temperatura" in msg


def test_build_current_forecast(monkeypatch):
    async def mock_fetch():
        return WeatherData(
            latitude=-7.31,
            longitude=-39.31,
            current=CurrentWeather(
                temperature_2m=30.0,
                relative_humidity_2m=40,
                rain=0,
                uv_index=8,
            ),
            daily=DailyWeather(temperature_2m_max=[34.0], temperature_2m_min=[22.0]),
        )

    monkeypatch.setattr("app.services.forecast.fetch_cariri_weather", mock_fetch)
    msg = asyncio.run(build_current_forecast())
    assert "Previsão" in msg
    assert "Alerta UV" in msg  # uv 8 → alert
