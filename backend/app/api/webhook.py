import logging
import time
import httpx
from evolution_api import EvolutionError
from fastapi import APIRouter, status, BackgroundTasks
from app.core.config import settings
from app.schemas.webhook import WebhookPayload
from app.services.forecast import build_current_forecast
from app.services.evolution_client import send_whatsapp_message
from app.services.whatsapp_session import check_whatsapp_status

logger = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/api/v1", tags=["Webhook"])

# dedupe: evolution fires per-instance + global webhook → same event twice
_seen_message_ids: dict[str, float] = {}
_SEEN_TTL_SECONDS = 300.0

def _is_duplicate(message_id: str) -> bool:
    now = time.monotonic()
    # drop expired
    expired = [k for k, t in _seen_message_ids.items() if now - t > _SEEN_TTL_SECONDS]
    for k in expired:
        _seen_message_ids.pop(k, None)
    if message_id in _seen_message_ids:
        return True
    _seen_message_ids[message_id] = now
    return False

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

HELP_TEXT = (
    "*🌤️ Clima-Zap — Comandos*\n\n"
    "• ```?```/```ajuda``` — esta lista\n"
    "• ```status``` — estado do bot e conexão WhatsApp\n"
    "• ```previsão``` — clima atual do Cariri\n\n"
    "Envie qualquer uma dessas opções."
)

NOT_FOUND_TEXT = (
    "❓ *Comando não reconhecido*\n\n"
    "Envie ```?``` ou ```ajuda``` para ver os comandos disponíveis."
)

FORECAST_ERROR_TEXT = (
    "⚠️ Não consegui buscar a previsão agora. Tente novamente em alguns instantes ou contate os desenvolvedores."
)


async def route_command(command: str) -> str:
    """Route incoming WhatsApp command to handler and return reply text."""
    if command in ("help", "?", "comandos", "ajuda"):
        return HELP_TEXT

    if command in ("status", "status?"):
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

    if command.startswith(("forecast", "previsao", "previsão", "previzao","previzão", "clima")):
        try:
            return await build_current_forecast()
        except (httpx.HTTPError, ValueError) as e:
            logger.error("Erro ao buscar previsão: %s", e)
            return FORECAST_ERROR_TEXT

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
    if message_id and _is_duplicate(message_id):
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
    response = await route_command(message_text.lower().strip())
    logger.info("Resposta (%s chars): %r...", len(response), response[:80])

    # DM: strip JID suffix (send_text expects plain number).
    # Group (@g.us): keep full JID so reply lands in the group.
    if sender.endswith("@g.us"):
        target = sender
    else:
        target = sender.split("@")[0]
    try:
        result = await send_whatsapp_message(target, response)
        logger.info("Enviado para %s: %s", target, result)
    except EvolutionError as e:
        logger.error("Erro ao enviar resposta para %s: %s", target, e)

@router.post("/webhook", status_code=status.HTTP_200_OK)
async def receive_webhook(payload: WebhookPayload, background_tasks: BackgroundTasks):
    """
    Receive WhatsApp webhook from Evolution API.
    
    SECURITY: Verify X-Hub-Signature header in production.
    """
    logger.info("Webhook: evento %r | instância %r", payload.event, payload.instance)
    background_tasks.add_task(process_event_background, payload)
    return {"status": "received", "reply": "ok"}