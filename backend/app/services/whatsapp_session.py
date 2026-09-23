import httpx

from app.core.config import settings


async def check_whatsapp_status() -> dict:
    """Query Evolution API instance connection state."""
    endpoint = (
        f"{settings.evolution_api_url.rstrip('/')}"
        f"/instance/connectionState/{settings.evolution_instance_name}"
    )

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                endpoint,
                headers={"apikey": settings.evolution_api_key},
            )
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, httpx.TimeoutException):
        return {"instance": {"state": "DISCONNECTED"}}
