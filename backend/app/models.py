from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Subscriber(Base):
    __tablename__ = "subscribers"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Local definido pelo bot (/configuracao): nome (cidade geocodificada ou
    # "lat, lon") + coordenadas; None = região padrão. Linhas antigas podem ter
    # só a cidade preset (sem coordenadas).
    city: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    # Horário personalizado de boletim para o grupo (formato "HH:MM"), ou None
    # para usar os horários globais (06/14/20h).
    bulletin_time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    # Inscrição modular: alertas climáticos (weather alerts) e boletins
    # periódicos (forecasts) são independentes — o usuário escolhe um,
    # outro ou ambos (ou nenhum, via /sair).
    receive_alerts: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    receive_bulletins: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
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


class AdminSession(Base):
    """Sessão administrativa de 7 dias, vinculada ao telefone que se registrou.

    O ``password_fingerprint`` invalida as sessões quando ``ADMIN_PASSWORD``
    muda: o hash é recalculado a cada autenticação e comparado no banco.
    """

    __tablename__ = "admin_sessions"

    phone: Mapped[str] = mapped_column(String(64), primary_key=True)
    password_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    registered_at: Mapped[float] = mapped_column(Float, nullable=False)
    expires_at: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    # None = aviso de expiração ainda não enviado (ou sessão renovada).
    notified_at: Mapped[float | None] = mapped_column(Float, nullable=True)