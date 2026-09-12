import logging
from fastapi import APIRouter, status, BackgroundTasks
from app.schemas.webhook import WebhookPayload

logger = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/api/v1", tags=["Webhook"])

async def process_event_background(payload: WebhookPayload):
    logger.info(f"Processando evento: {payload.event} | Instância: {payload.instance}")

@router.post("/webhook", status_code=status.HTTP_200_OK)
async def receive_webhook(payload: WebhookPayload, background_tasks: BackgroundTasks):
    logger.info(f"Webhook recebido: evento '{payload.event}' na instância '{payload.instance}'")
    background_tasks.add_task(process_event_background, payload)
    return {"status": "received", "reply": "ok"}  