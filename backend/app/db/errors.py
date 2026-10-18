"""Erros do backend de persistência ativo.

Docker persiste via SQLAlchemy; o Workers via D1. As camadas de serviço
precisam capturar o erro certo sem importar SQLAlchemy no bundle do Worker —
por isso a resolução é tardia, no momento em que a exceção aparece.
"""

from app.core import worker_runtime


def storage_errors() -> tuple[type[Exception], ...]:
    """Tipos de erro do storage atual (avaliados no ``except``, não no import).

    - Workers (binding D1 anexado): ``RuntimeError`` levantado por
      ``app.db.d1`` quando o binding não está disponível.
    - Docker/CPython: ``SQLAlchemyError`` (import tardio).
    """
    if worker_runtime.on_workers():
        return (RuntimeError,)
    from sqlalchemy.exc import SQLAlchemyError  # pylint: disable=import-outside-toplevel

    return (SQLAlchemyError,)
