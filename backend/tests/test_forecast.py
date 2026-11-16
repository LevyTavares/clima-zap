from datetime import datetime, timedelta

import asyncio

from app.formatter import (
    format_period_summary,
    format_window_summary,
    get_period_greeting,
    weather_code_to_text,
)
from app.schemas.schemas import (
    CurrentWeather,
    DailyWeather,
    HourlyWeather,
    MinutelyWeather,
    WeatherData,
)
from app.services.forecast import (
    PERIOD_HOURS,
    aggregate_period_hourly,
    build_comparison,
    build_current_forecast,
    build_period_forecast,
    build_weather_alerts,
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
    async def mock_fetch(_location=None):
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


def test_build_period_forecast_uses_group_location(monkeypatch):
    seen = {}

    async def mock_fetch(location=None):
        seen["location"] = location
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
    location = {"name": "Crato", "latitude": -7.2342, "longitude": -39.4086}

    msg = asyncio.run(build_period_forecast("morning", now=now, location=location))

    assert seen["location"] == location
    assert "Crato" in msg


def test_build_current_forecast(monkeypatch):
    async def mock_fetch(_location=None):
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


def test_build_current_forecast_janela_e_formato(monkeypatch):
    async def mock_fetch(_location=None):
        return WeatherData(
            latitude=-7.31,
            longitude=-39.31,
            current=CurrentWeather(
                temperature_2m=30.0,
                relative_humidity_2m=40,
                rain=0,
                uv_index=5,
            ),
            daily=DailyWeather(temperature_2m_max=[34.0], temperature_2m_min=[22.0]),
            hourly=_hourly_fixture(),
        )

    monkeypatch.setattr("app.services.forecast.fetch_cariri_weather", mock_fetch)
    now = datetime(2026, 9, 23, 13, 10)

    uma_hora = asyncio.run(build_current_forecast(now=now, window_minutes=60))
    # 13:10 → 14:10: horas 13h e 14h intersectam a janela (33 e 34) —
    # o bloco corrente entra: antes o filtro `now <= dt` o descartava.
    assert "Temperatura:* 33.0°C a 34.0°C\n" in uma_hora

    quatro_horas = asyncio.run(build_current_forecast(now=now, window_minutes=240))
    # 13:10 → 17:10: pontos 13..17h (33, 34, 20, 21, 22) → faixa real
    assert "Temperatura:* 20.0°C a 34.0°C" in quatro_horas


def _minutely_fixture() -> MinutelyWeather:
    """Blocos de 15 min a partir das 13:00: 30..33, depois 20..23."""
    base = datetime(2026, 9, 23, 13, 0)
    temps = [30.0, 31.0, 32.0, 33.0, 20.0, 21.0, 22.0, 23.0]
    return MinutelyWeather(
        time=[(base + timedelta(minutes=15 * i)).isoformat() for i in range(8)],
        temperature_2m=temps,
        precipitation_probability=[10.0, 20.0, 30.0, 40.0, 90.0, 80.0, 70.0, 60.0],
        relative_humidity_2m=[50.0] * 8,
        weather_code=[1] * 8,
    )


def test_janela_curta_usa_minutely_15(monkeypatch):
    async def mock_fetch(_location=None):
        return WeatherData(
            latitude=-7.31,
            longitude=-39.31,
            current=CurrentWeather(
                temperature_2m=30.0, relative_humidity_2m=40, rain=0, uv_index=5
            ),
            hourly=_hourly_fixture(),
            minutely_15=_minutely_fixture(),
        )

    monkeypatch.setattr("app.services.forecast.fetch_cariri_weather", mock_fetch)
    msg = asyncio.run(
        build_current_forecast(now=datetime(2026, 9, 23, 13, 10), window_minutes=60)
    )

    # 13:10 → 14:10 em blocos de 15 min: 30..33 e 20 → variação dentro da hora
    assert "Temperatura:* 20.0°C a 33.0°C" in msg
    assert "Chance de Chuva (pico):* 90%" in msg


def test_chuva_desconhecida_mostra_travessao(monkeypatch):
    async def mock_fetch(_location=None):
        return WeatherData(
            latitude=-7.31,
            longitude=-39.31,
            current=CurrentWeather(
                temperature_2m=30.0, relative_humidity_2m=40, rain=3.0, uv_index=5
            ),
        )

    monkeypatch.setattr("app.services.forecast.fetch_cariri_weather", mock_fetch)
    msg = asyncio.run(build_current_forecast(now=datetime(2026, 9, 23, 13, 10)))

    # rain é milímetro: sem série de chuva a chance é desconhecida, não 300%
    assert "Chance de Chuva (pico):* —" in msg


def test_formato_da_mensagem_do_clima_e_estavel(monkeypatch):
    """Contrato do texto: mudanças de tom/precisão passam a quebrar o teste."""
    monkeypatch.setattr("app.formatter.local_now", lambda: datetime(2026, 9, 23, 13, 0))

    msg = format_window_summary(
        city="Crato",
        temp_min=30.0,
        temp_max=33.0,
        humidity=45,
        uv_index=9.0,
        rain_prob=80,
        window_minutes=120,
    )

    assert msg == (
        "Boa tarde! 🌤️\n\n"
        "📍 *Previsão para Crato — próximos 2h*\n\n"
        "🌡️ *Temperatura:* 30.0°C a 33.0°C\n"
        "💧 *Umidade (média):* 45%\n"
        "🌧️ *Chance de Chuva (pico):* 80%\n"
        "🧴 *Índice UV (máx.):* 9.0 (_Muito Alto! Proteja-se do sol_)\n\n"
        "_Dica: Tempo fechado! Leve o guarda-chuva se for sair._ ☂️"
    )


def test_alerta_agendado_usa_a_janela_nao_o_instante():
    """Chuva a 90% na próxima hora alerta mesmo com o instante seco."""
    weather = WeatherData(
        latitude=-7.31,
        longitude=-39.31,
        current=CurrentWeather(
            temperature_2m=30.0, relative_humidity_2m=40, rain=0.0, uv_index=5
        ),
        minutely_15=_minutely_fixture(),
    )
    now = datetime(2026, 9, 23, 13, 10)

    alerts = build_weather_alerts(weather, now=now)

    assert any("Chuva Forte" in alert for alert in alerts)


def test_build_comparison_uma_linha_por_cidade(monkeypatch):
    seen = []

    async def mock_fetch(location=None):
        seen.append(location["name"])
        return WeatherData(
            latitude=-7.31,
            longitude=-39.31,
            current=CurrentWeather(
                temperature_2m=30.0, relative_humidity_2m=40, rain=0, uv_index=5
            ),
            hourly=_hourly_fixture(),
        )

    monkeypatch.setattr("app.services.forecast.fetch_cariri_weather", mock_fetch)
    locations = [
        {"name": "Barbalha", "latitude": -7.31, "longitude": -39.3},
        {"name": "Crato", "latitude": -7.23, "longitude": -39.4},
    ]
    msg = asyncio.run(build_comparison(locations, 120))

    assert seen == ["Barbalha", "Crato"]
    assert "Comparativo — próximos 2h" in msg
    assert "*Barbalha*:" in msg and "*Crato*:" in msg
    # compacto: sem saudação e sem dica por cidade
    assert "Boa " not in msg and "_Dica:" not in msg
