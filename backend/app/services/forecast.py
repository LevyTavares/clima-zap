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


def aggregate_period_hourly(hourly, period: Period, now: datetime | None = None) -> dict | None:
    """Agrega arrays horários do Open-Meteo no janela do período.

    hourly: HourlyWeather (ou dict-like com listas).
    Retorna None se não houver dados na janela.
    """
    now = now or datetime.now()
    times: list[str] = hourly.time or []
    if not times:
        return None

    temps: list[float] = hourly.temperature_2m
    pops: list[float] = hourly.precipitation_probability
    hums: list[float] = hourly.relative_humidity_2m
    uvs: list[float] = hourly.uv_index
    codes: list[int] = hourly.weather_code

    wanted = _period_date_ranges(period, now.date())
    selected_temps: list[float] = []
    selected_pops: list[float] = []
    selected_hums: list[float] = []
    selected_uvs: list[float] = []
    selected_codes: list[int] = []

    for idx, t in enumerate(times):
        try:
            dt = datetime.fromisoformat(t)
        except ValueError:
            continue
        for day, h_start, h_end in wanted:
            if dt.date() == day and h_start <= dt.hour < h_end:
                if idx < len(temps):
                    selected_temps.append(temps[idx])
                if idx < len(pops):
                    selected_pops.append(pops[idx])
                if idx < len(hums):
                    selected_hums.append(hums[idx])
                if idx < len(uvs):
                    selected_uvs.append(uvs[idx])
                if idx < len(codes):
                    selected_codes.append(codes[idx])
                break

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
