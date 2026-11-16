"""Builders de mensagem de previsão (comandos on-demand e boletim periódico)."""

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Literal

from app.api.api import fetch_cariri_weather
from app.core.clock import local_now
from app.core.config import settings
from app.core.location import LocationData
from app.formatter import (
    format_comparison,
    format_period_summary,
    format_window_summary,
)
from app.schemas.schemas import WeatherData
from app.services.alerts import ALERT_WINDOW_MINUTES, generate_weather_alerts

logger = logging.getLogger("uvicorn.error")

Period = Literal["morning", "afternoon", "night"]

# horas locais (America/Fortaleza) de cada período
PERIOD_HOURS: dict[Period, tuple[int, int]] = {
    # (start inclusive, end exclusive); night cruza meia-noite → resolve com 2 dias
    "morning": (6, 12),
    "afternoon": (12, 18),
    "night": (18, 6),
}


def _in_window(
    value: str, now: datetime, cutoff: datetime, step: timedelta
) -> bool:
    """O bloco ``value`` (de duração ``step``) intersecta [now, cutoff]?"""
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return False
    return moment <= cutoff and moment + step > now


def _window_values(
    times: list[str],
    values: list[float],
    now: datetime,
    cutoff: datetime,
    step: timedelta,
) -> list[float]:
    return [
        value
        for time_value, value in zip(times, values)
        if _in_window(time_value, now, cutoff, step)
    ]


def aggregate_window(
    weather: WeatherData, window_minutes: int, now: datetime
) -> dict:
    """Agrega a janela [agora, agora+N] em 15 min (≤4h) ou de hora em hora.

    O bloco do horário corrente entra (antes o filtro ``now <= dt`` o excluía,
    e a janela de 1h acabava descrevendo só a hora seguinte). Chuva sem dado
    vira ``None`` — ``rain`` é milímetro, não probabilidade.
    """
    cutoff = now + timedelta(minutes=window_minutes)
    cur = weather.current
    short = window_minutes <= 240
    source = weather.minutely_15 if short else weather.hourly
    if source is None or not source.time:
        source = weather.hourly
    step = timedelta(minutes=15) if source is weather.minutely_15 else timedelta(hours=1)

    temps: list[float] = []
    pops: list[float] = []
    hums: list[float] = []
    if source is not None and source.time:
        temps = _window_values(source.time, source.temperature_2m, now, cutoff, step)
        pops = _window_values(
            source.time, source.precipitation_probability, now, cutoff, step
        )
        hums = _window_values(
            source.time, source.relative_humidity_2m, now, cutoff, step
        )

    # UV não existe no minutely_15: usa o máximo horário da mesma janela.
    hourly = weather.hourly
    uvs = (
        _window_values(
            hourly.time, hourly.uv_index, now, cutoff, timedelta(hours=1)
        )
        if hourly is not None
        else []
    )

    return {
        "temp_min": min(temps) if temps else cur.temperature_2m,
        "temp_max": max(temps) if temps else cur.temperature_2m,
        "humidity": int(sum(hums) / len(hums)) if hums else int(cur.relative_humidity_2m),
        "rain_prob": int(max(pops)) if pops else None,
        "uv_index": max(uvs) if uvs else cur.uv_index,
    }


async def build_current_forecast(
    location: LocationData | None = None,
    window_minutes: int | None = None,
    now: datetime | None = None,
) -> str:
    """Forecast on-demand do comando `forecast` para os próximos N minutos."""
    if window_minutes is None:
        window_minutes = settings.forecast_window_minutes

    w = await fetch_cariri_weather(location)
    city = location["name"] if location else settings.default_city
    agg = aggregate_window(w, window_minutes, now or local_now())

    summary = format_window_summary(city=city, window_minutes=window_minutes, **agg)
    alerts = generate_weather_alerts(
        uv_index=agg["uv_index"],
        humidity=agg["humidity"],
        rain_prob=agg["rain_prob"],
    )
    if alerts:
        summary += "\n\n" + "\n".join(alerts)
    return summary


def build_weather_alerts(
    weather: WeatherData,
    window_minutes: int = ALERT_WINDOW_MINUTES,
    now: datetime | None = None,
) -> list[str]:
    """Alertas agendados: agregam a janela de 3h, não o instante atual.

    Mesma função de agregação do `/clima`, então os dois não discordam sobre o
    mesmo céu (o horizonte muda, a métrica não).
    """
    agg = aggregate_window(weather, window_minutes, now or local_now())
    return generate_weather_alerts(
        uv_index=agg["uv_index"],
        humidity=agg["humidity"],
        rain_prob=agg["rain_prob"],
    )


async def build_comparison(
    locations: list[LocationData], window_minutes: int | None = None
) -> str:
    """Comparativo compacto (uma linha por cidade) das janelas simultâneas."""
    window = window_minutes or settings.forecast_window_minutes
    now = local_now()
    weathers = await asyncio.gather(*(fetch_cariri_weather(loc) for loc in locations))
    rows = [
        {"city": loc["name"], **aggregate_window(w, window, now)}
        for loc, w in zip(locations, weathers)
    ]
    return format_comparison(rows, window)


def _period_date_ranges(period: Period, today: date) -> list[tuple[date, int, int]]:
    """Retorna [(date, start_hour, end_hour_exclusive)] para o período."""
    start, end = PERIOD_HOURS[period]
    if period == "night":
        # 18h hoje → 06h amanhã
        return [(today, start, 24), (today + timedelta(days=1), 0, end)]
    return [(today, start, end)]


def _matching_hour_indices(
    times: list[str], wanted: list[tuple[date, int, int]]
) -> list[int]:
    indices = []
    for index, time_value in enumerate(times):
        try:
            hour = datetime.fromisoformat(time_value)
        except ValueError:
            continue
        if any(
            hour.date() == day and start <= hour.hour < end
            for day, start, end in wanted
        ):
            indices.append(index)
    return indices


def aggregate_period_hourly(hourly, period: Period, now: datetime | None = None) -> dict | None:
    """Agrega arrays horários do Open-Meteo no janela do período.

    hourly: HourlyWeather (ou dict-like com listas).
    Retorna None se não houver dados na janela.
    """
    now = now or local_now()
    times: list[str] = hourly.time or []
    if not times:
        return None

    wanted = _period_date_ranges(period, now.date())
    selected_indices = _matching_hour_indices(times, wanted)
    hourly_values = (
        hourly.temperature_2m,
        hourly.precipitation_probability,
        hourly.relative_humidity_2m,
        hourly.uv_index,
        hourly.weather_code,
    )
    selected_values = [
        [values[index] for index in selected_indices if index < len(values)]
        for values in hourly_values
    ]
    selected_temps, selected_pops, selected_hums, selected_uvs, selected_codes = (
        selected_values
    )

    if not selected_temps and not selected_codes:
        return None

    return {
        "temp_min": min(selected_temps) if selected_temps else 0.0,
        "temp_max": max(selected_temps) if selected_temps else 0.0,
        "humidity_avg": int(sum(selected_hums) / len(selected_hums)) if selected_hums else 0,
        "rain_prob_max": max(selected_pops) if selected_pops else 0.0,
        "uv_max": max(selected_uvs) if selected_uvs else 0.0,
        "weather_codes": selected_codes or [0],
    }


async def build_period_forecast(
    period: Period,
    now: datetime | None = None,
    location: LocationData | None = None,
) -> str:
    """Boletim por período (manhã/tarde/noite) a partir do fetch horário.

    ``location`` None usa a região padrão; os grupos inscritos passam o próprio
    local para receber o boletim da cidade configurada neles.
    """
    w = await fetch_cariri_weather(location)
    if w.hourly is None:
        raise ValueError("Resposta sem dados horários")

    agg = aggregate_period_hourly(w.hourly, period, now=now)
    if agg is None:
        raise ValueError(f"Sem dados horários para período {period!r}")

    summary = format_period_summary(
        city=location["name"] if location else settings.default_city,
        period=period,
        temp_min=agg["temp_min"],
        temp_max=agg["temp_max"],
        humidity_avg=agg["humidity_avg"],
        rain_prob_max=agg["rain_prob_max"],
        uv_max=agg["uv_max"],
        weather_codes=agg["weather_codes"],
    )
    alerts = generate_weather_alerts(
        uv_index=agg["uv_max"],
        humidity=float(agg["humidity_avg"]),
        rain_prob=agg["rain_prob_max"],
    )
    if alerts:
        summary += "\n\n" + "\n".join(alerts)
    return summary
