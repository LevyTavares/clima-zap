import app.db.session as db_session
from app.models import AlertLog


async def record_alert_dispatch(
    alert_type: str,
    recipient: str,
    delivery_status: str,
    subscriber_id: int | None = None,
) -> None:
    async with db_session.SessionLocal() as session:
        session.add(
            AlertLog(
                alert_type=alert_type,
                recipient=recipient,
                delivery_status=delivery_status[:32],
                subscriber_id=subscriber_id,
            )
        )
        await session.commit()