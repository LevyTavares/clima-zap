"""Modelo de domínio independente do runtime (caminho D1/Workers).

O caminho Docker usa o mapeamento ORM (``app.models``), que importa SQLAlchemy.
O Worker precisa representar as linhas do D1 sem empacotar o SQLAlchemy (~9 MB
no bundle), então aqui ficam dataclasses puras: os consumidores (adaptador D1,
dispatcher de alertas, resolução de local) só leem os campos.
"""

from dataclasses import dataclass


@dataclass
class Subscriber:
    """Assinante — linha do D1 (Workers) ou do ORM (Docker), sem ORM aqui."""

    phone: str
    id: int | None = None
    name: str | None = None
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    is_active: bool = False
    receive_alerts: bool = False
    receive_bulletins: bool = False
    bulletin_time: str | None = None
    awaiting_gps: bool = False
    gps_expires_at: float | None = None
