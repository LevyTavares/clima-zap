"""O schema do D1 (``migrations/*.sql``) não pode divergir do ORM/Alembic.

O projeto tem duas verdades para o mesmo schema: o metadata do SQLAlchemy
(validado contra as migrations do Alembic pela CI, via ``alembic check``) e os
arquivos SQL aplicados no D1 pelo CD. Se alguém adicionar uma coluna só de um
lado, produção e ambiente local passam a discordar em silêncio — este teste barra.
"""

import sqlite3
from pathlib import Path

from app.db.base import Base
from app.models import AlertLog, Subscriber  # pylint: disable=unused-import

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"

# Tabelas que só existem no caminho Workers (estado do isolate → D1).
WORKERS_ONLY_TABLES = {"seen_messages", "dm_hints"}


def _d1_schema() -> dict[str, dict[str, bool]]:
    """Migrations do D1 num SQLite em memória: tabela → coluna → NOT NULL."""
    connection = sqlite3.connect(":memory:")
    try:
        migrations = sorted(MIGRATIONS_DIR.glob("*.sql"))
        assert migrations, "nenhuma migration SQL encontrada para o D1"
        for migration in migrations:
            connection.executescript(migration.read_text(encoding="utf-8"))
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        return {
            name: {
                row[1]: bool(row[3])
                for row in connection.execute(f"PRAGMA table_info({name})")
            }
            for (name,) in tables
            if not name.startswith("sqlite_")
        }
    finally:
        connection.close()


def test_tabelas_do_orm_existem_no_d1_com_as_mesmas_colunas():
    schema = _d1_schema()

    for name, table in Base.metadata.tables.items():
        assert name in schema, f"tabela {name!r} ausente nas migrations do D1"
        colunas_orm = {column.name for column in table.columns}
        assert set(schema[name]) == colunas_orm, (
            f"colunas divergentes em {name!r}: "
            f"ORM={sorted(colunas_orm)} D1={sorted(schema[name])}"
        )


def test_nulabilidade_das_colunas_compartilhadas_bate():
    schema = _d1_schema()

    for name, table in Base.metadata.tables.items():
        for column in table.columns:
            if column.primary_key:
                # No SQLite `INTEGER PRIMARY KEY` é alias de rowid: o PRAGMA
                # reporta notnull=0 mesmo com a coluna sendo NOT NULL.
                continue
            assert schema[name][column.name] is (not column.nullable), (
                f"{name}.{column.name}: NOT NULL do D1 difere do ORM"
            )


def test_tabelas_do_d1_sao_do_orm_ou_exclusivas_do_workers():
    schema = _d1_schema()
    conhecidas = set(Base.metadata.tables) | WORKERS_ONLY_TABLES

    inesperadas = set(schema) - conhecidas
    assert not inesperadas, f"tabelas inesperadas nas migrations do D1: {inesperadas}"
    assert WORKERS_ONLY_TABLES <= set(schema), (
        "tabelas exclusivas do Workers sumiram do D1"
    )
