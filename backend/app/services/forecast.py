"""Builders de mensagem de previsão (comandos on-demand e boletim periódico)."""

import logging
from datetime import date, datetime, timedelta
from typing import Literal

from app.api.api import fetch_cariri_weather
from app.core.config import settings
from app.core.location import LocationData
from app.formatter import (
    format_daily_summary,
    format_period_summary,
    format_window_summary,
)
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


async def build_current_forecast(
    location: LocationData | None = None, window_minutes: int | None = None
) -> str:
    """Forecast on-demand do comando `forecast` para os próximos N minutos."""
    from datetime import datetime, timedelta

    if window_minutes is None:
        window_minutes = settings.forecast_window_minutes

    w = await fetch_cariri_weather(location)
    city = location["name"] if location else settings.default_city
    cur = w.current
    now = datetime.now()
    cutoff = now + timedelta(minutes=window_minutes)

    temps: list[float] = []
    pops: list[float] = []
    hums: list[float] = []
    uvs: list[float] = []
    if w.hourly is not None and getattr(w.hourly, "time", None):
        for t, temp, pop, hum, uv in zip(
            w.hourly.time,
            w.hourly.temperature_2m or [],
            w.hourly.precipitation_probability or [],
            w.hourly.relative_humidity_2m or [],
            w.hourly.uv_index or [],
        ):
            try:
                dt = datetime.fromisoformat(t)
            except ValueError:
                continue
            if now <= dt <= cutoff:
                temps.append(temp)
                pops.append(pop)
                hums.append(hum)
                uvs.append(uv)

    if temps:
        temp_min = min(temps)
        temp_max = max(temps)
        rain_prob = int(max(pops)) if pops else int(cur.rain * 100)
        humidity = int(sum(hums) / len(hums)) if hums else int(cur.relative_humidity_2m)
        uv_index = max(uvs) if uvs else cur.uv_index
    else:
        temp_min = temp_max = cur.temperature_2m
        rain_prob = int(cur.rain * 100)
        humidity = int(cur.relative_humidity_2m)
        uv_index = cur.uv_index

    summary = format_window_summary(
        city=city,
        temp_min=temp_min,
        temp_max=temp_max,
        humidity=humidity,
        uv_index=uv_index,
        rain_prob=rain_prob,
        window_minutes=window_minutes,
    )
    alerts = generate_weather_alerts(
        uv_index=uv_index,
        humidity=humidity,
        rain_prob=rain_prob,
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
