"""Camada de dados: SQLAlchemy (Docker) ou D1 (Workers).

Sem reexports de propósito: importar ``app.db`` não pode arrastar o SQLAlchemy
para o bundle do Worker — o ORM fica atrás de ``app.db.orm`` (import tardio) e o
adaptador do D1 em ``app.db.d1``. O teste ``tests/test_worker_bundle.py``
protege essa fronteira.
"""
