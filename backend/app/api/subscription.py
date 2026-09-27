from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1", tags=["Subscription"])

# Base de dados em memória para demonstração (poderá ser substituída por base de dados real)
subscribers_db = set()

class SubscriptionPayload(BaseModel):
    phone: str = Field(..., description="Número de WhatsApp do utilizador")
    action: str = Field(..., description="Utilize 'subscribe' para inscrever ou 'unsubscribe' para cancelar")

@router.post("/subscribe", status_code=status.HTTP_200_OK)
async def manage_subscription(payload: SubscriptionPayload):
    """
    Gere a inscrição ou o cancelamento de utilizadores para alertas climáticos.
    """
    phone = payload.phone.strip()
    action = payload.action.lower().strip()

    if action == "subscribe":
        if phone in subscribers_db:
            return {"status": "already_subscribed", "message": f"O número {phone} já se encontra inscrito nos alertas."}
        subscribers_db.add(phone)
        return {"status": "success", "message": f"Inscrição efetuada com sucesso para o número {phone}."}
    
    elif action == "unsubscribe":
        if phone not in subscribers_db:
            return {"status": "not_found", "message": f"O número {phone} não foi encontrado na base de dados de inscritos."}
        subscribers_db.remove(phone)
        return {"status": "success", "message": f"Inscrição cancelada com sucesso para o número {phone}."}
    
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Ação inválida. Utilize 'subscribe' para inscrever ou 'unsubscribe' para cancelar."
    )