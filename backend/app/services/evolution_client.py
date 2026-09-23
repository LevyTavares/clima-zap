"""
Evolution API client for WhatsApp integration.
Uses evolution-whatsapp package for sending/receiving messages.
"""
import os
from evolution_api import EvoClient, jid


def get_evolution_client() -> EvoClient:
    """Get Evolution API client from env vars."""
    return EvoClient(
        base_url=os.getenv("EVOLUTION_API_URL", "http://localhost:8080"),
        api_key=os.getenv("EVOLUTION_API_KEY", ""),
        instance=os.getenv("EVOLUTION_INSTANCE_NAME", ""),
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
    return client.send_text(number, message)
