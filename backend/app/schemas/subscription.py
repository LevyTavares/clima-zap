from pydantic import BaseModel, Field

class SubscriptionPayload(BaseModel):
    phone: str = Field(..., description="Número de telemóvel ou WhatsApp do utilizador")
    action: str = Field(..., description="Ação pretendida: 'subscribe' para inscrever ou 'unsubscribe' para cancelar")