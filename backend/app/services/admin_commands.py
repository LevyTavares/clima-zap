"""Comandos administrativos do bot (``/admin <senha> <ação>``).

O comando só funciona no **privado**: em grupo o webhook responde como comando
desconhecido para não expor a existência da administração. A senha vem de
``ADMIN_PASSWORD`` (secreta no Worker, ``.env`` no Docker) e é comparada em
tempo constante. Opcionalmente ``ADMIN_PHONE`` limita o uso a um único número.

Ações disponíveis: ``status``, ``boletim [manha|tarde|noite]``, ``alertas``,
``grupos``, ``ping`` e ``ajuda``. As ações pesadas importam ``app.main``
tardiamente para não criar ciclo com o roteador do webhook.
"""

# pylint: disable=cyclic-import  # imports tardios de app.main evitam o ciclo

import logging
import secrets
import unicodedata
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.schedule import ALERT_SCHEDULE_HOURS, FORECAST_PERIOD_JOBS
from app.db.errors import storage_errors
from app.services.alert_history import recent_alert_dispatches
from app.services.persistence import list_active_groups, list_active_subscribers
from app.services.persistence import subscriber_location
from app.services.whatsapp_session import check_whatsapp_status

logger = logging.getLogger("uvicorn.error")

ADMIN_DISABLED_TEXT = (
    "🔒 *Administração desabilitada.*\n"
    "Defina `ADMIN_PASSWORD` no ambiente para habilitar o `/admin`."
)
INVALID_PASSWORD_TEXT = "❌ Senha administrativa inválida."
NO_PHONE_PERMISSION_TEXT = "❌ Este número não está autorizado a usar a administração."
ADMIN_USAGE_TEXT = (
    "Uso: `/admin <senha> <ação>`\n"
    "Envie `/admin <senha> ajuda` para ver as ações disponíveis."
)
ADMIN_HELP_TEXT = (
    "🛠️ *Clima-Zap — Administração*\n\n"
    "Uso: `/admin <senha> <ação>`\n\n"
    "• `status` — monitora API, WhatsApp, assinantes, grupos e últimos envios.\n"
    "• `boletim [manha|tarde|noite]` — dispara o boletim agora"
    " (sem período usa o atual).\n"
    "• `alertas` — executa o job de alertas agora.\n"
    "• `grupos` — lista os grupos inscritos e seus locais.\n"
    "• `ping` — teste rápido de resposta.\n"
    "• `ajuda` — esta mensagem.\n\n"
    "⚠️ Use somente no privado e apague a mensagem depois;"
    " a senha não deve ser enviada em grupos."
)

PERIOD_LABELS = {"morning": "manhã", "afternoon": "tarde", "night": "noite"}
PERIOD_ALIASES = {
    "manha": "morning",
    "morning": "morning",
    "tarde": "afternoon",
    "afternoon": "afternoon",
    "noite": "night",
    "night": "night",
}


def _normalize(text: str) -> str:
    """Minúsculas e sem acentos (``manhã`` → ``manha``)."""
    normalized = unicodedata.normalize("NFKD", text.strip().lower())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _digits(value: str) -> str:
    """Só os dígitos de um telefone/JID."""
    return "".join(char for char in value if char.isdigit())


def _now_brt() -> datetime:
    """Agora em BRT (America/Fortaleza = UTC-3 fixo, sem DST)."""
    return datetime.now(timezone.utc) - timedelta(hours=3)


def _format_brt(value: object) -> str:
    """Formata ``datetime``/string UTC do histórico como ``dd/mm HH:MM`` BRT."""
    if isinstance(value, str):
        try:
            moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    elif isinstance(value, datetime):
        moment = value
    else:
        return "?"
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return (moment.astimezone(timezone.utc) - timedelta(hours=3)).strftime(
        "%d/%m %H:%M"
    )


def _clip(text: str, limit: int = 3900) -> str:
    """Limita a resposta ao tamanho seguro de uma mensagem do WhatsApp."""
    if len(text) <= limit:
        return text
    return text[: limit - 20] + "\n… (mensagem truncada)"


def _authorize(args: str, recipient: str) -> tuple[str | None, str | None]:
    """Valida telefone (opcional) e senha; devolve (resto, erro)."""
    expected = settings.admin_password.get_secret_value()
    if not expected:
        return None, ADMIN_DISABLED_TEXT

    allowed_phone = _digits(settings.admin_phone)
    if allowed_phone and _digits(recipient) != allowed_phone:
        logger.warning("Admin recusado para %s: número fora da allowlist", recipient)
        return None, NO_PHONE_PERMISSION_TEXT

    password, _, rest = args.strip().partition(" ")
    if not password:
        return None, ADMIN_USAGE_TEXT
    if not secrets.compare_digest(
        password.encode("utf-8"), expected.encode("utf-8")
    ):
        logger.warning("Tentativa de /admin com senha inválida de %s", recipient)
        return None, INVALID_PASSWORD_TEXT
    return rest.strip(), None


def _format_groups(groups: list, limit: int) -> str:
    """Lista ``JID — cidade/coords`` (ou região padrão) com limite de linhas."""
    lines = []
    for subscriber in groups[:limit]:
        location = subscriber_location(subscriber)
        if location is None:
            place = f"região padrão ({settings.default_city})"
        else:
            place = (
                f"{location['name']} "
                f"({location['latitude']:.4f}, {location['longitude']:.4f})"
            )
        lines.append(f"• `{subscriber.phone}` — {place}")
    remaining = len(groups) - limit
    if remaining > 0:
        lines.append(f"… +{remaining} grupo(s)")
    return "\n".join(lines)


def _format_dispatch(row: dict) -> str:
    """Uma linha do histórico de envios."""
    return (
        f"• {_format_brt(row.get('sent_at'))} — "
        f"`{row.get('alert_type', '?')}` → "
        f"`{row.get('recipient', '?')}` "
        f"({row.get('delivery_status', '?')})"
    )


def _current_period() -> str:
    """Período do boletim de acordo com a hora BRT atual."""
    hour = _now_brt().hour
    if hour < 12:
        return "morning"
    if hour < 18:
        return "afternoon"
    return "night"


async def _status_text() -> str:
    """Monitoramento: WhatsApp, banco, assinantes, grupos, histórico e agenda."""
    wa = await check_whatsapp_status()
    instance = wa.get("instance") if isinstance(wa, dict) else None
    state = instance.get("state") if isinstance(instance, dict) else None
    state = state or (wa.get("state") if isinstance(wa, dict) else None)
    state = state or "DESCONHECIDO"

    try:
        subscribers = await list_active_subscribers()
        groups = [
            subscriber
            for subscriber in subscribers
            if subscriber.phone.endswith("@g.us")
        ]
        database = "ok"
    except storage_errors() as error:
        logger.error("Admin status: erro ao consultar assinantes: %s", error)
        subscribers, groups, database = [], [], "indisponível"

    try:
        recent = await recent_alert_dispatches(5)
    except storage_errors() as error:
        logger.error("Admin status: erro ao consultar histórico: %s", error)
        recent = []

    bulletin_hours = ", ".join(
        f"{hour:02d}h" for _, hour, _ in FORECAST_PERIOD_JOBS
    )
    alert_hours = ", ".join(f"{hour:02d}h" for hour in ALERT_SCHEDULE_HOURS)
    lines = [
        "🛠️ *Clima-Zap — Status administrativo*",
        "",
        f"• Ambiente: *{settings.environment}*",
        f"• Agora: *{_now_brt().strftime('%d/%m %H:%M')} BRT*",
        "• API: *online*",
        f"• WhatsApp: *{state}*",
        f"• Instância: `{settings.evolution_instance_name or '-'}`",
        f"• Grupo principal: `{settings.forecast_group_jid or 'não configurado'}`",
        f"• Banco: *{database}*",
        f"• Assinantes ativos: *{len(subscribers)}*"
        f" ({len(groups)} grupo(s), {len(subscribers) - len(groups)} PV)",
    ]
    if groups:
        lines.extend(["", f"*Grupos ({len(groups)}):*", _format_groups(groups, 10)])
    else:
        lines.extend(["", "*Grupos:* nenhum inscrito."])
    if recent:
        lines.extend(["", "*Últimos envios:*"])
        lines.extend(_format_dispatch(row) for row in recent)
    else:
        lines.extend(["", "*Últimos envios:* nenhum registro."])
    lines.extend(
        [
            "",
            "*Agenda (BRT):*",
            f"• Boletins: {bulletin_hours} (jitter 0–15min)",
            f"• Alertas: {alert_hours}",
        ]
    )
    return _clip("\n".join(lines))


async def _bulletin_text(params: str) -> str:
    """Dispara o boletim de um período agora (sem jitter)."""
    requested = _normalize(params)
    if requested:
        period = PERIOD_ALIASES.get(requested)
        if period is None:
            return "❌ Período inválido. Use `manha`, `tarde` ou `noite`."
    else:
        period = _current_period()

    # Import tardio: app.main importa este roteador (evita ciclo no import).
    from app.main import send_period_forecast  # pylint: disable=import-outside-toplevel

    try:
        summary = await send_period_forecast(period)
    except Exception as error:  # pylint: disable=broad-exception-caught
        logger.exception("Falha ao disparar boletim administrativo: %s", error)
        return "⚠️ Falha ao disparar o boletim. Veja os logs do Worker."

    label = PERIOD_LABELS[period]
    if summary["targets"] == 0:
        return (
            "⚠️ Nenhum destino configurado: `FORECAST_GROUP_JID` vazio e"
            " nenhum grupo inscrito."
        )
    failed = summary["failed"]
    suffix = f" Falha(s): {failed}." if failed else ""
    return (
        f"✅ Boletim da *{label}* disparado agora: "
        f"*{summary['sent']}/{summary['targets']}* envio(s).{suffix}"
    )


async def _alerts_text() -> str:
    """Executa o job de alertas agora (mesma rotina do Cron Trigger)."""
    from app.main import (  # pylint: disable=import-outside-toplevel
        process_scheduled_weather_alerts,
    )

    try:
        summary = await process_scheduled_weather_alerts()
    except Exception as error:  # pylint: disable=broad-exception-caught
        logger.exception("Falha ao executar alertas administrativos: %s", error)
        return "⚠️ Falha ao executar os alertas. Veja os logs do Worker."

    if summary["alerts"] == 0:
        return (
            f"✅ Alertas avaliados em *{summary['locations']}* local(is);"
            " nenhum alerta disparado agora."
        )
    return (
        f"✅ Alertas disparados: *{summary['alerts']}* alerta(s)"
        f" em *{summary['locations']}* local(is)."
    )


async def _groups_text() -> str:
    """Lista os grupos inscritos e o local de cada um."""
    try:
        groups = await list_active_groups()
    except storage_errors() as error:
        logger.error("Admin grupos: erro ao consultar grupos: %s", error)
        return "⚠️ Não consegui consultar os grupos agora."
    if not groups:
        return "ℹ️ Nenhum grupo inscrito no momento."
    return _clip("👥 *Grupos inscritos*\n\n" + _format_groups(groups, 20))


async def handle_admin_command(args: str, recipient: str) -> str:
    """Valida a senha e despacha a ação administrativa solicitada."""
    # pylint: disable=too-many-return-statements
    rest, error = _authorize(args, recipient)
    if error is not None:
        return error

    action, _, params = (rest or "").partition(" ")
    action = _normalize(action)
    if not action or action in ("ajuda", "help"):
        return ADMIN_HELP_TEXT

    logger.warning("Admin %s executou ação %r", recipient, action)
    if action == "ping":
        return (
            "🏓 *pong* — API online. "
            f"Agora: *{_now_brt().strftime('%d/%m %H:%M')} BRT*."
        )
    if action in ("status", "monitor"):
        return await _status_text()
    if action in ("boletim", "forecast"):
        return await _bulletin_text(params)
    if action in ("alertas", "alerts"):
        return await _alerts_text()
    if action in ("grupos", "groups"):
        return await _groups_text()
    return ADMIN_USAGE_TEXT
