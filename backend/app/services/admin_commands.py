"""Comandos administrativos do bot.

Fluxo principal: ``/admin register <senha>`` autentica uma vez e libera o
número por 7 dias; depois as ações (``/admin status``, ``/admin boletim`` etc.)
funcionam sem repetir a senha. A sessão fica no D1/Postgres e expira sozinha;
um job periódico avisa o número quando ela vence. O formato antigo
``/admin <senha> <ação>`` continua aceito para uso avulso.

O comando só funciona no **privado**: em grupo o webhook responde como comando
desconhecido para não expor a existência da administração. A senha vem de
``ADMIN_PASSWORD`` (secreta no Worker, ``.env`` no Docker) e é comparada em
tempo constante. Opcionalmente ``ADMIN_PHONE`` limita o uso a um único número.

Ações disponíveis: ``status``, ``boletim [manha|tarde|noite]``, ``alertas``,
``grupos``, ``ping``, ``logout`` e ``ajuda``. As ações pesadas importam
``app.main`` tardiamente para não criar ciclo com o roteador do webhook.
"""

# pylint: disable=cyclic-import  # imports tardios de app.main evitam o ciclo

import logging
import secrets
import unicodedata
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.schedule import ALERT_SCHEDULE_HOURS, FORECAST_PERIOD_JOBS
from app.db.errors import storage_errors
from app.services.admin_sessions import (
    ADMIN_SESSION_DAYS,
    get_admin_session,
    password_fingerprint,
    register_admin_session,
    revoke_admin_session,
)
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
ADMIN_AUTH_REQUIRED_TEXT = (
    "🔒 *Sessão administrativa necessária.*\n"
    "Envie `/admin register <senha>` no privado para liberar este número"
    f" por {ADMIN_SESSION_DAYS} dias."
)
ADMIN_REGISTER_USAGE_TEXT = "Uso: `/admin register <senha>`."
ADMIN_USAGE_TEXT = (
    "Uso: `/admin register <senha>` (libera este número por"
    f" {ADMIN_SESSION_DAYS} dias).\n"
    "Depois: `/admin <ação>` — ex.: `/admin status` ou `/admin ping`."
)
ADMIN_HELP_TEXT = (
    "🛠️ *Clima-Zap — Administração*\n\n"
    "🔐 Acesso: `/admin register <senha>` libera este número por"
    f" {ADMIN_SESSION_DAYS} dias.\n"
    "Depois use `/admin <ação>` sem a senha.\n\n"
    "• `status` — monitora API, WhatsApp, assinantes, grupos e últimos envios.\n"
    "• `boletim [manha|tarde|noite]` — dispara o boletim agora"
    " (sem período usa o atual).\n"
    "• `alertas` — executa o job de alertas agora.\n"
    "• `grupos` — lista os grupos inscritos e seus locais.\n"
    "• `ping` — teste rápido de resposta.\n"
    "• `logout` — encerra a sessão deste número.\n"
    "• `ajuda` — esta mensagem.\n\n"
    "⚠️ Use somente no privado; a senha só é necessária no registro."
)

KNOWN_ACTIONS = frozenset(
    {
        "status",
        "monitor",
        "boletim",
        "forecast",
        "alertas",
        "alerts",
        "grupos",
        "groups",
        "ping",
        "ajuda",
        "help",
        "logout",
        "sair",
    }
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


def _format_epoch_brt(epoch: float) -> str:
    """Formata um epoch UTC como ``dd/mm/aaaa HH:MM`` BRT (UTC-3 fixo)."""
    moment = datetime.fromtimestamp(epoch, tz=timezone.utc) - timedelta(hours=3)
    return moment.strftime("%d/%m/%Y %H:%M")


def _clip(text: str, limit: int = 3900) -> str:
    """Limita a resposta ao tamanho seguro de uma mensagem do WhatsApp."""
    if len(text) <= limit:
        return text
    return text[: limit - 20] + "\n… (mensagem truncada)"


def _admin_password() -> str:
    """Senha administrativa configurada (string vazia = desabilitado)."""
    return settings.admin_password.get_secret_value()


def _phone_allowed(recipient: str) -> bool:
    """True se ``ADMIN_PHONE`` está vazio ou bate com o remetente."""
    allowed_phone = _digits(settings.admin_phone)
    return not allowed_phone or _digits(recipient) == allowed_phone


def _check_password(password: str, recipient: str) -> str | None:
    """Valida configuração, allowlist e senha; devolve erro ou None."""
    expected = _admin_password()
    if not expected:
        return ADMIN_DISABLED_TEXT
    if not _phone_allowed(recipient):
        logger.warning("Admin recusado para %s: número fora da allowlist", recipient)
        return NO_PHONE_PERMISSION_TEXT
    if not password:
        return ADMIN_REGISTER_USAGE_TEXT
    if not secrets.compare_digest(
        password.encode("utf-8"), expected.encode("utf-8")
    ):
        logger.warning("Tentativa de /admin com senha inválida de %s", recipient)
        return INVALID_PASSWORD_TEXT
    return None


async def _require_session(recipient: str) -> tuple[dict | None, str | None]:
    """Valida a sessão ativa do número; devolve (sessão, erro)."""
    expected = _admin_password()
    if not expected:
        return None, ADMIN_DISABLED_TEXT
    if not _phone_allowed(recipient):
        logger.warning("Admin recusado para %s: número fora da allowlist", recipient)
        return None, NO_PHONE_PERMISSION_TEXT
    try:
        session = await get_admin_session(
            recipient, password_fingerprint(expected)
        )
    except storage_errors() as error:
        logger.error("Erro ao validar sessão admin de %s: %s", recipient, error)
        return None, "⚠️ Não consegui validar a sessão administrativa agora."
    if session is None:
        return None, ADMIN_AUTH_REQUIRED_TEXT
    return session, None


def _register_password(params: str) -> str:
    """Senha do ``/admin register``; aceita o prefixo ``--`` da documentação."""
    password = params.strip()
    if password.startswith("--"):
        password = password[2:].strip()
    return password


async def _register(params: str, recipient: str) -> str:
    """Autentica a senha e cria/renova a sessão de 7 dias deste número."""
    if not _admin_password():
        return ADMIN_DISABLED_TEXT
    password = _register_password(params)
    if not password:
        return ADMIN_REGISTER_USAGE_TEXT
    error = _check_password(password, recipient)
    if error is not None:
        return error

    try:
        expires_at = await register_admin_session(
            recipient, password_fingerprint(_admin_password())
        )
    except storage_errors() as storage_error:
        logger.error(
            "Erro ao registrar sessão admin de %s: %s", recipient, storage_error
        )
        return "⚠️ Não consegui registrar a sessão agora. Tente novamente."

    expires = _format_epoch_brt(expires_at)
    logger.warning("Admin %s registrou sessão até %s BRT", recipient, expires)
    return (
        "✅ *Administração liberada para este número.*\n"
        f"Válida por *{ADMIN_SESSION_DAYS} dias* — expira em *{expires} BRT*.\n\n"
        "Use `/admin status`, `/admin boletim`, `/admin alertas`,"
        " `/admin grupos` ou `/admin ping` sem a senha.\n"
        "Para encerrar antes: `/admin logout`."
    )


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


async def _status_text(session: dict | None = None) -> str:
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
    if session is not None:
        lines.append(
            "• Sessão admin: expira em "
            f"*{_format_epoch_brt(float(session['expires_at']))} BRT*"
        )
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


async def _dispatch(
    action: str, params: str, recipient: str, session: dict | None = None
) -> str:
    """Executa uma ação já autenticada (sessão ou senha avulsa)."""
    # pylint: disable=too-many-return-statements
    action = _normalize(action)
    if not action or action in ("ajuda", "help"):
        return ADMIN_HELP_TEXT

    if action in ("logout", "sair"):
        try:
            revoked = await revoke_admin_session(recipient)
        except storage_errors() as error:
            logger.error("Erro ao encerrar sessão admin de %s: %s", recipient, error)
            return "⚠️ Não consegui encerrar a sessão agora."
        if not revoked:
            return "ℹ️ Nenhuma sessão administrativa ativa."
        logger.warning("Admin %s encerrou a sessão", recipient)
        return (
            "✅ Sessão administrativa encerrada.\n"
            "Envie `/admin register <senha>` para abrir outra."
        )

    logger.warning("Admin %s executou ação %r", recipient, action)
    if action == "ping":
        return (
            "🏓 *pong* — API online. "
            f"Agora: *{_now_brt().strftime('%d/%m %H:%M')} BRT*."
        )
    if action in ("status", "monitor"):
        return await _status_text(session=session)
    if action in ("boletim", "forecast"):
        return await _bulletin_text(params)
    if action in ("alertas", "alerts"):
        return await _alerts_text()
    if action in ("grupos", "groups"):
        return await _groups_text()
    return ADMIN_USAGE_TEXT


async def handle_admin_command(args: str, recipient: str) -> str:
    """Autentica (registro ou sessão) e despacha a ação administrativa."""
    # pylint: disable=too-many-return-statements
    raw = args.strip()
    first, _, rest = raw.partition(" ")
    action = _normalize(first)

    if action in ("register", "registrar"):
        return await _register(rest, recipient)

    if action in KNOWN_ACTIONS:
        session, error = await _require_session(recipient)
        if error is not None:
            return error
        return await _dispatch(action, rest.strip(), recipient, session=session)

    # Compatibilidade: `/admin <senha> <ação>` (uso avulso, sem criar sessão).
    if not raw:
        return ADMIN_USAGE_TEXT
    legacy_action, _, legacy_params = rest.strip().partition(" ")
    error = _check_password(first, recipient)
    if error is not None:
        return error
    if not _normalize(legacy_action):
        return ADMIN_USAGE_TEXT
    return await _dispatch(legacy_action, legacy_params, recipient)
