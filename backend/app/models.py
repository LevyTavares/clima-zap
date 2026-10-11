from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Subscriber(Base):
    __tablename__ = "subscribers"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    alert_logs: Mapped[list["AlertLog"]] = relationship(back_populates="subscriber")


class AlertLog(Base):
    __tablename__ = "alert_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    alert_type: Mapped[str] = mapped_column(String(64), index=True)
    delivery_status: Mapped[str] = mapped_column(String(32))
    recipient: Mapped[str] = mapped_column(String(128))
    subscriber_id: Mapped[int | None] = mapped_column(
        ForeignKey("subscribers.id", ondelete="SET NULL"), nullable=True
    )
    subscriber: Mapped[Subscriber | None] = relationship(back_populates="alert_logs")