"""Erros do backend de persistência ativo.

Docker persiste via SQLAlchemy; o Workers via D1. As camadas de serviço
precisam capturar o erro certo sem importar SQLAlchemy no bundle do Worker —
por isso a resolução é tardia, no momento em que a exceção aparece.
"""

from app.core import worker_runtime


def storage_errors() -> tuple[type[Exception], ...]:
    """Tipos de erro do storage atual (avaliados no ``except``, não no import).

    - Workers (Pyodide): ``RuntimeError`` — inclusive se o env ainda não foi
      anexado, porque o SQLAlchemy nunca existe no bundle do Worker (evita
      mascarar a falha real com ``No module named 'sqlalchemy'``).
    - Docker/CPython: ``SQLAlchemyError`` (import tardio).
    """
    if worker_runtime.is_workers_runtime() or worker_runtime.on_workers():
        return (RuntimeError,)
    from sqlalchemy.exc import SQLAlchemyError  # pylint: disable=import-outside-toplevel

    return (SQLAlchemyError,)
