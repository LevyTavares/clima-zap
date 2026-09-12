import logging
from fastapi import APIRouter, status, BackgroundTasks
from app.schemas.webhook import WebhookPayload

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/api/v1", tags=["Webhook"])

async def process_event_background(payload: WebhookPayload):
    # Lote de processamento assíncrono em segundo plano para evitar timeout no provedor
    logger.info(f"Processando evento em background: {payload.event} | Instância: {payload.instance}")
    # Insira aqui a lógica de negócio do Clima-Zap (ex: salvar mensagem, disparar IA, etc.)

@router.post("/webhook", status_code=status.HTTP_200_OK)
async def receive_webhook(payload: WebhookPayload, background_tasks: BackgroundTasks):
    logger.info(f"Webhook recebido com sucesso: evento '{payload.event}' na instância '{payload.instance}'")
    
    # Delega o processamento pesado para background tasks, retornando 200 OK imediatamente
    background_tasks.add_task(process_event_background, payload)
    
    return {"status": "received"}