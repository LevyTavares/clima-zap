"""Builders de mensagem de previsão (comandos on-demand e boletim periódico)."""

import logging
from datetime import date, datetime, timedelta
from typing import Literal

from app.api.api import fetch_cariri_weather
from app.core.config import settings
from app.formatter import format_daily_summary, format_period_summary
from app.services.alerts import generate_weather_alerts

logger = logging.getLogger("uvicorn.error")

Period = Literal["morning", "afternoon", "night"]

# horas locais (America/Fortaleza) de cada período
PERIOD_HOURS: dict[Period, tuple[int, int]] = {
    # (start inclusive, end exclusive); night cruza meia-noite → resolve com 2 dias
    "morning": (6, 12),
    "afternoon": (12, 18),
    "night": (18, 6),
}


async def build_current_forecast() -> str:
    """Forecast on-demand do comando `forecast` (resumo diário + alertas)."""
    w = await fetch_cariri_weather()
    cur = w.current
    temp_max = (
        w.daily.temperature_2m_max[0]
        if w.daily and w.daily.temperature_2m_max
        else cur.temperature_2m
    )
    temp_min = (
        w.daily.temperature_2m_min[0]
        if w.daily and w.daily.temperature_2m_min
        else cur.temperature_2m
    )
    summary = format_daily_summary(
        city=settings.default_city,
        temp_min=temp_min,
        temp_max=temp_max,
        humidity=int(cur.relative_humidity_2m),
        uv_index=cur.uv_index,
        rain_prob=int(cur.rain * 100),
    )
    alerts = generate_weather_alerts(
        uv_index=cur.uv_index,
        humidity=cur.relative_humidity_2m,
        rain_prob=int(cur.rain * 100),
    )
    if alerts:
        summary += "\n\n" + "\n".join(alerts)
    return summary


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
    now = now or datetime.now()
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


async def build_period_forecast(period: Period, now: datetime | None = None) -> str:
    """Boletim por período (manhã/tarde/noite) a partir do fetch horário."""
    w = await fetch_cariri_weather()
    if w.hourly is None:
        raise ValueError("Resposta sem dados horários")

    agg = aggregate_period_hourly(w.hourly, period, now=now)
    if agg is None:
        raise ValueError(f"Sem dados horários para período {period!r}")

    summary = format_period_summary(
        city=settings.default_city,
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
