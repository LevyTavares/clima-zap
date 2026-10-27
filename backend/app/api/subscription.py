from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services.persistence import subscribe_recipient, unsubscribe_recipient

router = APIRouter(prefix="/api/v1", tags=["Subscription"])

class SubscriptionPayload(BaseModel):
    phone: str = Field(..., description="Número de WhatsApp do utilizador")
    name: str | None = Field(default=None, max_length=120, description="Nome do utilizador")
    action: str = Field(..., description="Utilize 'subscribe' para inscrever ou 'unsubscribe' para cancelar")
    types: str | list[str] | None = Field(
        default=None,
        description="Tipos de inscrição: 'alertas', 'boletins', 'todos' (padrão) ou lista.",
    )

@router.post("/subscribe", status_code=status.HTTP_200_OK)
async def manage_subscription(payload: SubscriptionPayload):
    """
    Gerencia a inscrição ou o cancelamento de utilizadores para alertas climáticos
    e boletins periódicos (inscrição modular).
    """
    phone = payload.phone.strip()
    action = payload.action.lower().strip()

    if action == "subscribe":
        return await subscribe_recipient(phone, payload.name, payload.types)

    if action == "unsubscribe":
        return await unsubscribe_recipient(phone, payload.types)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Ação inválida. Utilize 'subscribe' para inscrever ou 'unsubscribe' para cancelar.",
    )
