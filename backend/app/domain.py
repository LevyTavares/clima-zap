"""Modelo de domínio independente do runtime (caminho D1/Workers).

O caminho Docker usa o mapeamento ORM (``app.models``), que importa SQLAlchemy.
O Worker precisa representar as linhas do D1 sem empacotar o SQLAlchemy (~9 MB
no bundle), então aqui fica a dataclass pura, gerada da mesma lista de colunas
que o adaptador D1 usa (``app.db.columns``) — os consumidores (adaptador D1,
dispatcher de alertas, resolução de local) só leem os campos.
"""

from dataclasses import field, make_dataclass

from app.db.columns import SUBSCRIBER_COLUMNS


def _field(column):
    if column.required:
        return (column.name, column.py_type)
    # field() é consumido pelo make_dataclass logo abaixo
    # pylint: disable-next=invalid-field-call
    return (column.name, column.py_type, field(default=column.default))


Subscriber = make_dataclass(
    "Subscriber",
    [_field(column) for column in SUBSCRIBER_COLUMNS],
    namespace={
        "__doc__": "Assinante — linha do D1 (Workers) ou do ORM (Docker), sem ORM aqui."
    },
)
