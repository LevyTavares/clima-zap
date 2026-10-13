# backend/app/services/persistence.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models import Subscriber, AlertLog  # Ajuste conforme seus modelos reais

async def save_subscriber(db: AsyncSession, phone_number: str, city: str) -> Subscriber:
    """Salva ou atualiza um assinante do Clima-Zap no banco de dados."""
    result = await db.execute(select(Subscriber).filter(Subscriber.phone_number == phone_number))
    subscriber = result.scalars().first()
    
    if subscriber:
        subscriber.city = city
    else:
        subscriber = Subscriber(phone_number=phone_number, city=city)
        db.add(subscriber)
        
    await db.commit()
    await db.refresh(subscriber)
    return subscriber

async def log_alert_dispatch(db: AsyncSession, subscriber_id: int, alert_type: str, message: str) -> AlertLog:
    """Registra o histórico de alertas disparados para auditoria e controle."""
    alert_log = AlertLog(
        subscriber_id=subscriber_id,
        alert_type=alert_type,
        message=message
    )
    db.add(alert_log)
    await db.commit()
    await db.refresh(alert_log)
    return alert_log