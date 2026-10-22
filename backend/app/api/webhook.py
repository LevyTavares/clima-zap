# pylint: disable=duplicate-code,broad-exception-caught,line-too-long,missing-module-docstring,missing-function-docstring
import logging
from fastapi import APIRouter, HTTPException, Request, status

from app.core.location import get_location_coords, match_city, parse_coordinates
from app.services.evolution_client import send_whatsapp_message
from app.services.forecast import build_current_forecast

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["webhook"])

NUMERIC_CITY_MAP = {
    "1": "Barbalha",
    "2": "Juazeiro do Norte",
    "3": "Crato",
}

NATURAL_KEYWORDS = ["clima", "tempo", "chuva", "sol", "previsao", "previsão"]


def normalize_text(text: str) -> str:
    return text.strip().lower()


def parse_intent(message_text: str) -> tuple[str, str | None]:
    """Identifica a intenção do usuário por comandos com barra, números ou palavras-chave."""
    raw = normalize_text(message_text)

    # 1. Comandos com barra
    if raw.startswith("/"):
        parts = raw.split(maxsplit=1)
        cmd = parts[0]
        arg = parts[1] if len(parts) > 1 else None
        return cmd, arg

    # 2. Atalhos numéricos de cidade
    if raw in NUMERIC_CITY_MAP:
        return "/configuracao", NUMERIC_CITY_MAP[raw]

    # 3. Linguagem natural sem barra
    if any(kw in raw for kw in NATURAL_KEYWORDS):
        return "/clima", None

    return "/desconhecido", raw


@router.post("/webhook")
async def handle_whatsapp_webhook(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payload inválido")

    if not body or body.get("event") != "messages.upsert":
        return {"status": "ignored"}

    data = body.get("data", {})
    key = data.get("key", {})

    if key.get("fromMe"):
        return {"status": "ignored"}

    remote_jid = key.get("remoteJid")
    message_content = data.get("message", {})
    text = message_content.get("conversation") or message_content.get("extendedTextMessage", {}).get("text", "")

    if not remote_jid or not text:
        return {"status": "no_action"}

    cmd, arg = parse_intent(text)

    try:
        if cmd in ("/clima", "/tempo"):
            loc = get_location_coords(arg) or get_location_coords("barbalha")
            try:
                reply = await build_current_forecast(loc)
            except Exception as exc:
                logger.error("Erro na busca da previsão: %s", exc)
                reply = "Ops! Tivemos uma instabilidade momentânea ao consultar a previsão do tempo. Tente novamente em alguns minutinhos! 🌤️"

            await send_whatsapp_message(remote_jid, reply)

        elif cmd in ("/configuracao", "/cidade"):
            if not arg:
                reply = (
                    "Escolha sua cidade respondendo com o número:\n"
                    "1️⃣ - Barbalha\n"
                    "2️⃣ - Juazeiro do Norte\n"
                    "3️⃣ - Crato\n\n"
                    "Ou digite: `/configuracao <nome da cidade>`"
                )
            else:
                coords = parse_coordinates(arg)
                loc = coords or get_location_coords(arg) or match_city(arg)

                if loc:
                    reply = f"📍 Localização configurada com sucesso para: *{loc['name']}*!"
                else:
                    reply = (
                        "Não encontrei essa localização. Tente selecionar pelo número:\n"
                        "1️⃣ - Barbalha | 2️⃣ - Juazeiro do Norte | 3️⃣ - Crato"
                    )

            await send_whatsapp_message(remote_jid, reply)

        elif cmd == "/ajuda":
            reply = (
                "🤖 *Clima-Zap - Menu de Comandos*\n\n"
                "• Digite *1*, *2* ou *3* para definir sua cidade rapidamente:\n"
                "  1 - Barbalha | 2 - Juazeiro do Norte | 3 - Crato\n"
                "• Digite *tempo*, *clima* ou *vai chover?* para ver a previsão.\n"
                "• Ou use `/clima` e `/configuracao <cidade>`."
            )
            await send_whatsapp_message(remote_jid, reply)

    except Exception as err:
        logger.error("Erro no processamento da mensagem do webhook: %s", err)
        await send_whatsapp_message(
            remote_jid,
            "Ops! Ocorreu um erro temporário ao processar sua solicitação. Tente novamente em instantes! 🌤️",
        )

    return {"status": "processed"}