"""Porta única para o SQLAlchemy — import tardio, exclusivo do caminho Docker.

O bundle do Worker (``backend/pyproject.toml``) não inclui SQLAlchemy: nenhum
módulo do caminho Pyodide pode importar este aqui. As camadas de serviço o
importam **dentro** do ramo ``worker_runtime.on_workers() is False``.
"""

from sqlalchemy import delete, select, text

from app.models import AlertLog, Subscriber

__all__ = ["AlertLog", "Subscriber", "delete", "select", "text"]
