import httpx

from app.core.config import settings


async def check_whatsapp_status() -> dict:
    endpoint = (
        f"{settings.whatsapp_api_url.rstrip('/')}"
        f"/instance/connectionState/{settings.whatsapp_instance_name}"
    )

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                endpoint,
                headers={"apikey": settings.whatsapp_api_key},
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError:
        return {"state": "DISCONNECTED"}
