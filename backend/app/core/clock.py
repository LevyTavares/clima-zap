"""Relógio do projeto em America/Fortaleza (UTC-3, sem DST desde 2019).

O runtime dos Workers roda em UTC e os containers não definem `TZ`: qualquer
`datetime.now()` cru desloca janelas, períodos, saudações e o `/agendar` em 3h.
"""

from datetime import datetime, timedelta, timezone

FORTRALEZA_TZ = timezone(timedelta(hours=-3))


def local_now() -> datetime:
    """Agora em America/Fortaleza, naive (séries do Open-Meteo vêm sem tz)."""
    return datetime.now(timezone.utc).astimezone(FORTRALEZA_TZ).replace(tzinfo=None)
