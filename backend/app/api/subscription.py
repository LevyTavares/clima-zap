from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import Subscriber

router = APIRouter(prefix="/api/v1", tags=["Subscription"])

class SubscriptionPayload(BaseModel):
    phone: str = Field(..., description="Número de WhatsApp do utilizador")
    name: str | None = Field(default=None, max_length=120, description="Nome do utilizador")
    action: str = Field(..., description="Utilize 'subscribe' para inscrever ou 'unsubscribe' para cancelar")

@router.post("/subscribe", status_code=status.HTTP_200_OK)
async def manage_subscription(
    payload: SubscriptionPayload,
    db: AsyncSession = Depends(get_db),
):
    """
    Gere a inscrição ou o cancelamento de utilizadores para alertas climáticos.
    """
    phone = payload.phone.strip()
    action = payload.action.lower().strip()
    result = await db.execute(select(Subscriber).where(Subscriber.phone == phone))
    subscriber = result.scalar_one_or_none()

    if action == "subscribe":
        if subscriber and subscriber.is_active:
            return {"status": "already_subscribed", "message": f"O número {phone} já se encontra inscrito nos alertas."}
        if subscriber:
            subscriber.is_active = True
            if payload.name is not None:
                subscriber.name = payload.name.strip() or None
        else:
            db.add(Subscriber(phone=phone, name=payload.name.strip() if payload.name else None))
        await db.commit()
        return {"status": "success", "message": f"Inscrição efetuada com sucesso para o número {phone}."}
    
    if action == "unsubscribe":
        if subscriber is None or not subscriber.is_active:
            return {"status": "not_found", "message": f"O número {phone} não foi encontrado na base de dados de inscritos."}
        subscriber.is_active = False
        await db.commit()
        return {"status": "success", "message": f"Inscrição cancelada com sucesso para o número {phone}."}
    
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Ação inválida. Utilize 'subscribe' para inscrever ou 'unsubscribe' para cancelar."
    )