# pylint: disable=duplicate-code,broad-exception-caught,line-too-long,missing-module-docstring,missing-function-docstring,too-many-branches,too-many-return-statements,too-many-locals,too-many-statements,raise-missing-from,unused-argument,redefined-outer-name,reimported,unused-import,possibly-used-before-assignment
import asyncio
import logging
import secrets
from functools import partial

import httpx
from evolution_api import EvolutionError
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, status

from app.core import worker_runtime
from app.core.config import settings
from app.core.geocode import geocode_city
from app.core.location import (
    CITY_OPTIONS,
    CRAJUBAR_LOCATIONS,
    LocationData,
    NUMERIC_CITY_MAP,
    match_city,
    parse_coordinates,
)
from app.schemas.webhook import WebhookPayload
from app.services.admin_commands import handle_admin_command
from app.services.bot_menu import get_help_message
from app.services.command_parser import parse_invocation
from app.services.evolution_client import send_whatsapp_message
from app.services.forecast import build_current_forecast
from app.services.persistence import (
    clear_subscriber_location,
    get_subscriber_location,
    is_duplicate_message,
    set_subscriber_location,
    should_hint_dm,
    subscribe_recipient,
    unsubscribe_recipient,
)
from app.services.whatsapp_session import check_whatsapp_status

logger = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/api/v1", tags=["Webhook"])


def extract_message_content(data: dict) -> str:
    """Extract text message from Evolution API data payload."""
    message = data.get("message", {})
    if "conversation" in message:
        return message["conversation"]
    if "extendedTextMessage" in message:
        return message["extendedTextMessage"].get("text", "")
    return ""


def extract_sender_jid(data: dict) -> str:
    """Extract sender JID from Evolution API data payload."""
    key = data.get("key", {})
    return key.get("remoteJid", "")


def extract_mentioned_jids(data: dict) -> list[str]:
    """JIDs mencionados na mensagem (contextInfo da Evolution/Baileys)."""
    message = data.get("message") or {}
    extended = message.get("extendedTextMessage") or {}
    context = extended.get("contextInfo") or {}
    raw = context.get("mentionedJid") or context.get("mentionKey") or []
    return [jid for jid in raw if isinstance(jid, str)]


def extract_location(data: dict) -> tuple[float, float, str | None] | None:
    """Extrai latitude, longitude e nome/endereço de um payload de localização."""
    message = data.get("message") or {}
    loc_msg = message.get("locationMessage") or message.get("liveLocationMessage") or {}
    if not loc_msg:
        return None

    lat = loc_msg.get("degreesLatitude") if "degreesLatitude" in loc_msg else loc_msg.get("latitude")
    lon = loc_msg.get("degreesLongitude") if "degreesLongitude" in loc_msg else loc_msg.get("longitude")

    if lat is None or lon is None:
        return None

    try:
        name = loc_msg.get("name") or loc_msg.get("address") or None
        return float(lat), float(lon), name
    except (ValueError, TypeError):
        return None


NOT_FOUND_TEXT = (
    "❓ *Comando não reconhecido*\n\n"
    "Envie ```/ajuda``` para ver os comandos disponíveis."
)

FORECAST_ERROR_TEXT = (
    "⚠️ Não consegui buscar a previsão agora. Tente novamente em alguns instantes ou contate os desenvolvedores."
)

FORECAST_ALIASES = (
    "forecast",
    "previsao",
    "previsão",
    "previzao",
    "previzão",
    "clima",
)

HINT_TEXT = (
    "🤖 Eu sou o *Clima-Zap*! Envie ```/ajuda``` para ver os comandos"
    " (ex: ```/clima```)."
)


def recipient_key(sender: str) -> str:
    """DM → só dígitos (send_text espera número puro); grupo (@g.us) → JID completo."""
    return sender if sender.endswith("@g.us") else sender.split("@")[0]


def _location_summary(location: LocationData | None) -> str:
    """Linha de resumo do local atual (ou da região padrão)."""
    if location is None:
        return f"📍 Nenhum local definido — padrão: *{settings.default_city}*."
    return (
        f"📍 Local atual: *{location['name']}*"
        f" ({location['latitude']:.4f}, {location['longitude']:.4f})"
    )


async def _show_location(recipient: str) -> str:
    """Comando sem argumentos: mostra o local atual e as opções numeradas."""
    location = await get_subscriber_location(recipient)
    numbered = "\n".join(f"{emoji} {name}" for emoji, _, name in CITY_OPTIONS)
    return (
        f"{_location_summary(location)}\n"
        "Escolha a cidade da região Crajubar (envie o número):\n"
        f"{numbered}\n"
        "Ou use ```/configuracao <cidade | lat,lon>``` "
        "(ex: ```/configuracao Crato``` ou ```/configuracao 2```)."
    )


async def _apply_city(recipient: str, city_query: str) -> str:
    """Resolve a cidade (preset do Crajubar ou geocoder) e grava como local."""
    location = match_city(city_query) or await geocode_city(city_query)
    if location is None:
        options = ", ".join(item["name"] for item in CRAJUBAR_LOCATIONS.values())
        return (
            f"❓ Local não encontrado: *{city_query}*.\n"
            f"Cidades de referência: {options}.\n"
            "Também use coordenadas: ```/configuracao -7.23, -39.31```."
        )
    await set_subscriber_location(
        recipient, location["name"], location["latitude"], location["longitude"]
    )
    return (
        f"✅ Local configurado: *{location['name']}*!\n"
        "Envie ```/clima``` para ver a previsão da sua região."
    )


async def handle_city_command(city_query: str, recipient: str) -> str:
    """Comando `/cidade [nome]` — atalho de /configuracao para cidades."""
    if not city_query:
        return await _show_location(recipient)
    return await _apply_city(recipient, city_query)


async def handle_config_command(args: str, recipient: str) -> str:
    """Comando `/configuracao [cidade | lat,lon | padrao]`."""
    query = args.strip()
    if not query:
        return await _show_location(recipient)

    if query.lower() in ("padrao", "padrão", "reset", "default"):
        await clear_subscriber_location(recipient)
        return f"✅ Local removido — voltou ao padrão *{settings.default_city}*."

    coordinates = parse_coordinates(query)
    if coordinates is not None:
        await set_subscriber_location(
            recipient,
            coordinates["name"],
            coordinates["latitude"],
            coordinates["longitude"],
        )
        return (
            f"✅ Coordenadas definidas: *{coordinates['name']}*!\n"
            "Envie ```/clima``` para ver a previsão da sua região."
        )

    return await _apply_city(recipient, query)


async def handle_comparar_command() -> str:
    """Comando `/comparar`: previsão simultânea das 3 cidades do Crajubar."""
    try:
        locs = [
            match_city("barbalha"),
            match_city("juazeiro do norte"),
            match_city("crato"),
        ]
        forecasts = await asyncio.gather(
            *[build_current_forecast(loc) for loc in locs if loc is not None]
        )
        return (
            "📊 *Comparativo Regional - Crajubar*\n\n"
            f"1️⃣ {forecasts[0]}\n\n"
            f"2️⃣ {forecasts[1]}\n\n"
            f"3️⃣ {forecasts[2]}"
        )
    except Exception as exc:
        logger.error("Erro ao comparar regiões: %s", exc)
        return FORECAST_ERROR_TEXT


async def handle_status_command() -> str:
    """Comando `status`: estado da API e da instância WhatsApp."""
    wa = await check_whatsapp_status()
    state = (
        wa.get("instance", {}).get("state")
        or wa.get("state")
        or "DESCONHECIDO"
    )
    return (
        "*🤖 Clima-Zap — Status*\n\n"
        "• API: *online*\n"
        f"• WhatsApp: *{state}*\n"
        f"• Instância: `{settings.evolution_instance_name or '-'}`"
    )


async def handle_agendar_command(recipient: str, args: str = "") -> str:
    """Agenda um boletim personalizado para o grupo (formato HH:MM)."""
    from app.services.persistence import set_bulletin_time

    if not recipient.endswith("@g.us"):
        return "ℹ️ O agendamento de boletins é feito em grupos."

    query = (args or "").strip().lower()
    if query in ("off", "cancelar", "desativar", "none"):
        await set_bulletin_time(recipient, None)
        return "✅ Boletim personalizado desativado para este grupo."

    if not query:
        return (
            "ℹ️ Use ```/agendar HH:MM``` (ex: ```/agendar 06:30```) "
            "ou ```/agendar off``` para desativar."
        )

    parts = query.replace(".", ":").split(":")
    if len(parts) != 2:
        return "❌ Formato inválido. Use HH:MM (ex: 06:30)."
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return "❌ Formato inválido. Use HH:MM (ex: 06:30)."
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return "❌ Horário inválido. Use HH:MM (ex: 06:30)."
    time_str = f"{hour:02d}:{minute:02d}"
    await set_bulletin_time(recipient, time_str)
    return f"✅ Boletim personalizado agendado para {time_str} neste grupo."


async def handle_subscription_command(command: str, recipient: str, args: str = "") -> str:
    """Comandos `inscrever` / `sair`: ativa ou cancela alertas e/ou boletins."""
    kinds_arg = args.strip() if args else None

    if command == "inscrever":
        result = await subscribe_recipient(recipient, kinds=kinds_arg)
        if result["status"] == "already_subscribed":
            return "ℹ️ " + result["message"].replace("já está inscrito", "já está inscrito")
        return "✅ " + result["message"]

    result = await unsubscribe_recipient(recipient, kinds=kinds_arg)
    if result["status"] == "not_found":
        return "ℹ️ Este contato não possui inscrição ativa nos tipos solicitados."
    return "✅ " + result["message"]


async def handle_forecast_command(recipient: str) -> str:
    """Comando de previsão: usa o local do /configuracao (ou região padrão)."""
    location = await get_subscriber_location(recipient)
    try:
        return await build_current_forecast(location)
    except (httpx.HTTPError, ValueError) as e:
        logger.error("Erro ao buscar previsão: %s", e)
        return FORECAST_ERROR_TEXT


async def handle_non_command(recipient: str) -> str | None:
    """Texto sem comando: em grupo o bot fica calado; no privado responde a dica de /ajuda."""
    if recipient.endswith("@g.us"):
        return None
    if not await should_hint_dm(recipient):
        return None
    return HINT_TEXT


async def route_command(command: str, args: str, recipient: str) -> str:
    """Roteia o comando já parseado (ver command_parser) e retorna a resposta."""
    if command in ("help", "?", "comandos", "ajuda"):
        return get_help_message()

    if command in ("status", "status?"):
        return await handle_status_command()

    if command == "cidade":
        return await handle_city_command(args, recipient)

    if command in ("configuracao", "configuração", "config"):
        return await handle_config_command(args, recipient)

    if command in ("comparar", "crajubar"):
        return await handle_comparar_command()

    if command in ("inscrever", "sair"):
        return await handle_subscription_command(command, recipient, args)

    if command == "agendar":
        return await handle_agendar_command(recipient, args)

    if command in FORECAST_ALIASES:
        return await handle_forecast_command(recipient)

    if command == "admin":
        if recipient.endswith("@g.us"):
            logger.warning("Comando /admin recusado em grupo: %s", recipient)
            return NOT_FOUND_TEXT
        return await handle_admin_command(args, recipient)

    return NOT_FOUND_TEXT


def normalize_event(event: str) -> str:
    """Normalize event name: 'messages.upsert' / 'MESSAGES_UPSERT' → 'messages_upsert'."""
    return event.strip().lower().replace("-", "_").replace(".", "_")


async def process_event_background(payload: WebhookPayload):
    """Process incoming Evolution API webhook event."""
    logger.info("Evento recebido: %s | Instância: %s", payload.event, payload.instance)

    if normalize_event(payload.event) != "messages_upsert":
        return

    data = payload.data
    if not isinstance(data, dict):
        logger.warning("messages.upsert com data inesperado: %s", type(data))
        return

    key = data.get("key", {})
    if key.get("fromMe"):
        return

    message_id = key.get("id", "")
    if message_id and await is_duplicate_message(message_id):
        logger.info("Duplicado ignorado: %s", message_id)
        return

    message_text = extract_message_content(data)
    sender = extract_sender_jid(data)

    loc_data = extract_location(data)
    if loc_data and sender:
        recipient = recipient_key(sender)
        lat, lon, loc_name = loc_data
        name_to_set = loc_name or f"GPS ({lat:.2f}, {lon:.2f})"
        await set_subscriber_location(recipient, name_to_set, lat, lon)
        response = (
            f"📍 Localização GPS recebida e salva: *{name_to_set}*!\n"
            "Envie ```/clima``` para ver a previsão do tempo atualizada."
        )
        try:
            await send_whatsapp_message(recipient, response)
        except EvolutionError as e:
            logger.error("Erro ao enviar confirmação de GPS para %s: %s", recipient, e)
        return

    if not message_text or not sender:
        logger.info(
            "Vazio — text=%r sender=%r message_type=%r",
            message_text,
            sender,
            data.get("messageType"),
        )
        return

    recipient = recipient_key(sender)
    invocation = parse_invocation(message_text, extract_mentioned_jids(data))
    admin_password = settings.admin_password.get_secret_value()
    admin_attempt = (
        invocation is not None and invocation.command == "admin"
    ) or (bool(admin_password) and admin_password in message_text)
    if admin_attempt:
        logger.info("Mensagem de %s: /admin (credenciais omitidas)", sender)
    else:
        logger.info("Mensagem de %s: %s", sender, message_text)

    if invocation is None:
        response = await handle_non_command(recipient)
        if response is None:
            logger.info("Texto sem comando — silêncio: %s", recipient)
            return
    else:
        response = await route_command(invocation.command, invocation.args, recipient)
    logger.info("Resposta (%s chars): %r...", len(response), response[:80])

    try:
        result = await send_whatsapp_message(recipient, response)
        logger.info("Enviado para %s: %s", recipient, result)
    except EvolutionError as e:
        logger.error("Erro ao enviar resposta para %s: %s", recipient, e)


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def receive_webhook(
    payload: WebhookPayload,
    background_tasks: BackgroundTasks,
    authorization: str = Header(default=""),
):
    """Receive WhatsApp webhook from Evolution API."""
    expected = settings.webhook_auth_token
    if not expected:
        if settings.is_production:
            logger.error(
                "Webhook recusado: WEBHOOK_AUTH_TOKEN não configurado em produção"
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Webhook auth not configured",
            )
    else:
        provided = authorization.encode("utf-8")
        wanted = f"Bearer {expected}".encode("utf-8")
        if not secrets.compare_digest(provided, wanted):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook token",
            )
    logger.info("Webhook: evento %r | instância %r", payload.event, payload.instance)
    if not worker_runtime.defer(partial(process_event_background, payload)):
        background_tasks.add_task(process_event_background, payload)
    return {"status": "received", "reply": "ok"}