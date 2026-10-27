"""Agendamento dos jobs — fonte única para APScheduler (Docker) e Workers.

Reúne o que os dois caminhos precisam compartilhar sem importar FastAPI nem o
runtime do workerd (testável no CPython):

- faixa de horas e jitter dos jobs (APScheduler e Cron Triggers);
- hora BRT → período do boletim (Cron Triggers);
- decisão de qual job cada expressão de cron do Worker dispara;
- sorteio do atraso anti-spam, limitado pelo wall time de um Cron Trigger.
"""

import random

from app.services.forecast import Period

# Alertas: 06/08/12/14/16/18h BRT (America/Fortaleza = UTC-3, sem DST).
ALERT_SCHEDULE_HOURS = [6, 8, 12, 14, 16, 18]

# Alertas climáticos: jitter 0–5min anti-spam (evita rajada simultânea).
ALERT_JITTER_SECONDS = 300  # 5min

# Boletim periódico: manhã / tarde / noite — jitter 0–15min anti-spam.
FORECAST_PERIOD_JOBS: list[tuple[str, int, Period]] = [
    ("forecast_morning", 6, "morning"),
    ("forecast_afternoon", 14, "afternoon"),
    ("forecast_night", 20, "night"),
]
FORECAST_JITTER_SECONDS = 900  # 15min

# Hora BRT → período do boletim (usado pelos Cron Triggers do Workers).
FORECAST_PERIOD_BY_HOUR: dict[int, Period] = {
    hour: period for _, hour, period in FORECAST_PERIOD_JOBS
}

# Manutenção diária (purge do histórico de alert_logs). 20h BRT só é atingida
# pela expressão dos boletins — ver ``cron_dispatch`` —, então o job não colide
# com os alertas.
MAINTENANCE_HOUR = 20

# Expressões em `triggers.crons` do wrangler.jsonc (em UTC). Os dois crons de
# alertas/boletins coincidem em 06h e 14h BRT — ver ``cron_dispatch``.
ALERTS_CRON = "0 9,11,15,17,19,21 * * *"
BULLETINS_CRON = "0 9,17,23 * * *"
# Aviso de sessão administrativa expirada: roda a cada 5min (o vencimento cai
# em qualquer minuto; não há como agendar um cron por sessão no Workers).
ADMIN_SESSION_CHECK_MINUTES = 5
ADMIN_SESSION_CRON = "*/5 * * * *"
# Boletins personalizados por grupo: verificação a cada minuto.
CUSTOM_BULLETIN_CRON = "* * * * *"
CRON_EXPRESSIONS = (ALERTS_CRON, BULLETINS_CRON, ADMIN_SESSION_CRON, CUSTOM_BULLETIN_CRON)

# Cron Triggers têm 15min de wall time por invocação. O jitter dorme dentro do
# próprio handler, então reservamos uma margem para o envio (HTTP + D1) caber
# no limite mesmo quando o sorteio é o maior possível.
CRON_WALL_TIME_LIMIT_SECONDS = 900
CRON_JITTER_MARGIN_SECONDS = 60


def jitter_delay_seconds(
    max_seconds: int = FORECAST_JITTER_SECONDS,
    rng: random.Random | None = None,
) -> float:
    """Atraso anti-spam sorteado em ``[0, max_seconds]`` (0 se desativado).

    Espelha o ``jitter`` do APScheduler no caminho Docker, mas nunca passa do
    wall time de um Cron Trigger menos a margem de segurança — o sleep
    acontece no próprio handler ``scheduled``.
    """
    ceiling = min(
        max_seconds, CRON_WALL_TIME_LIMIT_SECONDS - CRON_JITTER_MARGIN_SECONDS
    )
    if ceiling <= 0:
        return 0.0
    return (rng or random).uniform(0, ceiling)


def cron_dispatch(cron: str) -> tuple[bool, bool]:
    """Diz se a expressão ``cron`` deve disparar (alertas, boletins).

    Sem esse despacho o handler rodaria duas vezes em 06h e 14h BRT (as duas
    expressões coincidem nesses horários) duplicando alertas e boletins.
    Expressões desconhecidas caem no despacho por hora, como antes; o cron de
    sessão administrativa é conhecido e não dispara nenhum dos dois.
    """
    cron = (cron or "").strip()
    if cron not in CRON_EXPRESSIONS:
        return True, True
    if cron == CUSTOM_BULLETIN_CRON:
        return False, False
    return cron == ALERTS_CRON, cron == BULLETINS_CRON


def is_admin_session_cron(cron: str) -> bool:
    """True para a expressão que verifica sessões administrativas vencidas."""
    return (cron or "").strip() == ADMIN_SESSION_CRON


def is_custom_bulletin_cron(cron: str) -> bool:
    """True para a expressão que dispara boletins personalizados por grupo."""
    return (cron or "").strip() == CUSTOM_BULLETIN_CRON
