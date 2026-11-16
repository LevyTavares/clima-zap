"""Colunas de `subscribers` — fonte única do domínio e do adaptador D1.

O caminho Docker mapeia as mesmas colunas no ORM (`app/models.py`), que o
Alembic lê; o Worker não pode importar SQLAlchemy, então o dataclass de
domínio, a conversão de linha do D1 e o SQL de INSERT/UPDATE saem daqui.
`tests/test_storage_schema.py` falha se esta lista divergir do ORM.

Novo campo: acrescente aqui, no ORM e nas duas migrations (D1 + Alembic).
"""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class Column:
    """Coluna de domínio + conversor aplicado ao valor que vem do D1."""

    name: str
    py_type: Any
    default: Any = None
    converter: Callable[[Any], Any] | None = None
    required: bool = False


def _flag(value: Any) -> bool:
    """SQLite devolve 0/1; o domínio usa bool."""
    return bool(value)


SUBSCRIBER_COLUMNS: tuple[Column, ...] = (
    Column("phone", str, required=True),
    Column("id", int | None),
    Column("name", str | None),
    Column("city", str | None),
    Column("latitude", float | None),
    Column("longitude", float | None),
    Column("is_active", bool, False, _flag),
    Column("receive_alerts", bool, False, _flag),
    Column("receive_bulletins", bool, False, _flag),
    Column("bulletin_time", str | None),
    Column("awaiting_gps", bool, False, _flag),
    Column("gps_expires_at", float | None),
    Column("window_minutes", int | None),
)
