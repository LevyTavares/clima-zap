"""
Evolution API client for WhatsApp integration.
Uses evolution-whatsapp package for sending/receiving messages.

Usa o ``AsyncEvoClient``: o request HTTP acontece fora do event loop (obrigatório
no Cloudflare Workers, que não tolera bloqueio síncrono durante I/O).
"""
from evolution_api import AsyncEvoClient, jid

from app.core.config import settings


def get_evolution_client() -> AsyncEvoClient:
    """Get Evolution API client from settings (.env at repo root)."""
    return AsyncEvoClient(
        base_url=settings.evolution_api_url,
        api_key=settings.evolution_api_key,
        instance=settings.evolution_instance_name,
    )


def format_phone_jid(phone: str) -> str:
    """Format phone number to WhatsApp JID."""
    return jid(phone)


async def send_whatsapp_message(number: str, message: str) -> dict:
    """Send text message via Evolution API.

    number: plain digits with country code (e.g. '558897169894'),
            or full group JID ending in '@g.us' (kept as-is).
    """
    if "@g.us" not in number:
        number = number.split("@")[0]
    client = get_evolution_client()
    return await client.send_text(number, message)
