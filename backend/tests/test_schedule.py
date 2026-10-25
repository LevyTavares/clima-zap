"""Testes do agendamento compartilhado (``app.core.schedule``).

Cobrem o que difere entre o caminho Docker (APScheduler com ``jitter``) e o
Cloudflare Workers (Cron Triggers): o sorteio do atraso anti-spam dentro do
limite de wall time do Cron Trigger e o despacho por expressão de cron — que
evita duplicar alertas e boletins nas horas em que os dois crons coincidem.
"""

import json
import random

from app.core import schedule
from app.core.config import ROOT_DIR

WRANGLER_CONFIG = ROOT_DIR / "backend" / "wrangler.jsonc"


def _wrangler_crons() -> list[str]:
    """Lê ``triggers.crons`` do wrangler.jsonc (JSONC: remove comentários //)."""
    raw = WRANGLER_CONFIG.read_text(encoding="utf-8")
    without_comments = "\n".join(
        line.split("//", maxsplit=1)[0] for line in raw.splitlines()
    )
    return json.loads(without_comments)["triggers"]["crons"]


def _cron_hours(expression: str) -> list[int]:
    """Horas UTC (segundo campo) de uma expressão de cron."""
    return [int(hour) for hour in expression.split()[1].split(",")]


def _utc_to_brt(hours: list[int]) -> list[int]:
    """Converte horas UTC em horas BRT (America/Fortaleza = UTC-3 fixo)."""
    return [(hour - 3) % 24 for hour in hours]


def test_jitter_delay_sorteia_dentro_do_intervalo():
    rng = random.Random(20260801)

    delays = [
        schedule.jitter_delay_seconds(schedule.FORECAST_JITTER_SECONDS, rng=rng)
        for _ in range(200)
    ]

    assert all(0.0 <= delay <= schedule.FORECAST_JITTER_SECONDS for delay in delays)
    assert len(set(delays)) > 1  # é sorteio, não valor fixo


def test_jitter_delay_respeita_wall_time_do_cron():
    ceiling = (
        schedule.CRON_WALL_TIME_LIMIT_SECONDS - schedule.CRON_JITTER_MARGIN_SECONDS
    )
    rng = random.Random(7)

    delays = [schedule.jitter_delay_seconds(3600, rng=rng) for _ in range(200)]

    assert all(delay <= ceiling for delay in delays)


def test_jitter_delay_zero_quando_desligado():
    assert schedule.jitter_delay_seconds(0) == 0.0
    assert schedule.jitter_delay_seconds(-1) == 0.0


def test_cron_dispatch_nao_duplica_alertas_e_boletins():
    # 06h e 14h BRT: os dois crons coincidem — cada um dispara só o seu job.
    assert schedule.cron_dispatch(schedule.ALERTS_CRON) == (True, False)
    assert schedule.cron_dispatch(schedule.BULLETINS_CRON) == (False, True)


def test_cron_dispatch_da_sessao_admin_nao_dispara_outros_jobs():
    assert schedule.cron_dispatch(schedule.ADMIN_SESSION_CRON) == (False, False)
    assert schedule.is_admin_session_cron(schedule.ADMIN_SESSION_CRON) is True
    assert schedule.is_admin_session_cron(schedule.ALERTS_CRON) is False


def test_cron_dispatch_expressao_desconhecida_cai_no_filtro_por_hora():
    assert schedule.cron_dispatch("0 9 * * *") == (True, True)
    assert schedule.cron_dispatch("") == (True, True)


def test_crons_do_wrangler_espelham_as_constantes():
    crons = _wrangler_crons()

    assert crons == [
        schedule.ALERTS_CRON,
        schedule.BULLETINS_CRON,
        schedule.ADMIN_SESSION_CRON,
    ]


def test_horas_utc_dos_crons_equivalem_as_horas_brt():
    assert _utc_to_brt(_cron_hours(schedule.ALERTS_CRON)) == schedule.ALERT_SCHEDULE_HOURS
    assert _utc_to_brt(_cron_hours(schedule.BULLETINS_CRON)) == sorted(
        schedule.FORECAST_PERIOD_BY_HOUR
    )


def test_manutencao_pega_carona_na_hora_exclusiva_dos_boletins():
    """O purge diário (20h BRT) não pode coincidir com uma hora de alertas."""
    assert schedule.MAINTENANCE_HOUR in schedule.FORECAST_PERIOD_BY_HOUR
    assert schedule.MAINTENANCE_HOUR not in schedule.ALERT_SCHEDULE_HOURS


def test_verificacao_de_sessao_admin_roda_a_cada_5min():
    assert schedule.ADMIN_SESSION_CHECK_MINUTES == 5
    assert schedule.ADMIN_SESSION_CRON == "*/5 * * * *"
