import logging
import secrets
import httpx
from evolution_api import EvolutionError
from fastapi import APIRouter, Header, status, BackgroundTasks, HTTPException
from app.core.config import settings
from app.core.geocode import geocode_city
from app.core.location import CRAJUBAR_LOCATIONS, LocationData, match_city, parse_coordinates
from app.schemas.webhook import WebhookPayload
from app.services.bot_menu import get_help_message
from app.services.command_parser import parse_invocation
from app.services.forecast import build_current_forecast
from app.services.evolution_client import send_whatsapp_message
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
    """Comando sem argumentos: mostra o local atual e como alterá-lo."""
    location = await get_subscriber_location(recipient)
    return (
        f"{_location_summary(location)}\n"
        "Envie ```/configuracao <cidade | lat,lon>``` para alterar"
        " (ex: ```/configuracao Crato```)."
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


async def handle_subscription_command(command: str, recipient: str) -> str:
    """Comandos `inscrever` / `sair`: ativa ou cancela os alertas do remetente."""
    if command == "inscrever":
        result = await subscribe_recipient(recipient)
        if result["status"] == "already_subscribed":
            return "ℹ️ Este contato já está inscrito nos alertas climáticos."
        return "✅ Inscrição realizada! Você receberá os alertas climáticos da sua cidade."

    result = await unsubscribe_recipient(recipient)
    if result["status"] == "not_found":
        return "ℹ️ Este contato não possui inscrição ativa nos alertas."
    return "✅ Inscrição cancelada — você não receberá mais alertas climáticos."


async def handle_forecast_command(recipient: str) -> str:
    """Comando de previsão: usa o local do /configuracao (ou região padrão)."""
    location = await get_subscriber_location(recipient)
    try:
        return await build_current_forecast(location)
    except (httpx.HTTPError, ValueError) as e:
        logger.error("Erro ao buscar previsão: %s", e)
        return FORECAST_ERROR_TEXT


async def handle_non_command(recipient: str) -> str | None:
    """Texto sem comando: em grupo o bot fica calado; no privado responde a
    dica de /ajuda uma única vez por contato."""
    if recipient.endswith("@g.us"):
        return None
    if not await should_hint_dm(recipient):
        return None
    return HINT_TEXT


async def route_command(command: str, args: str, recipient: str) -> str:
    """Roteia o comando já parseado (ver command_parser) e retorna a resposta."""
    # pylint: disable=too-many-return-statements
    if command in ("help", "?", "comandos", "ajuda"):
        return get_help_message()

    if command in ("status", "status?"):
        return await handle_status_command()

    if command == "cidade":
        return await handle_city_command(args, recipient)

    if command in ("configuracao", "configuração", "config"):
        return await handle_config_command(args, recipient)

    if command in ("inscrever", "sair"):
        return await handle_subscription_command(command, recipient)

    if command in FORECAST_ALIASES:
        return await handle_forecast_command(recipient)

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
        return  # ignore own messages / echoes

    message_id = key.get("id", "")
    if message_id and await is_duplicate_message(message_id):
        logger.info("Duplicado ignorado: %s", message_id)
        return

    message_text = extract_message_content(data)
    sender = extract_sender_jid(data)

    if not message_text or not sender:
        logger.info(
            "Vazio — text=%r sender=%r message_type=%r",
            message_text,
            sender,
            data.get("messageType"),
        )
        return

    logger.info("Mensagem de %s: %s", sender, message_text)
    recipient = recipient_key(sender)
    invocation = parse_invocation(message_text, extract_mentioned_jids(data))
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
    """
    Receive WhatsApp webhook from Evolution API.

    SECURITY: quando WEBHOOK_AUTH_TOKEN está definido, exige
    `Authorization: Bearer <token>` (configure como header customizado no
    webhook da instância da Evolution API).
    """
    expected = settings.webhook_auth_token
    if expected:
        provided = authorization.encode("utf-8")
        wanted = f"Bearer {expected}".encode("utf-8")
        if not secrets.compare_digest(provided, wanted):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook token",
            )
    logger.info("Webhook: evento %r | instância %r", payload.event, payload.instance)
    background_tasks.add_task(process_event_background, payload)
    return {"status": "received", "reply": "ok"}
