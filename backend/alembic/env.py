import asyncio
from logging.config import fileConfig

from alembic import context as alembic_context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import normalized_database_url, settings
from app.models import Subscriber

config = getattr(alembic_context, "config")
database_url = normalized_database_url(settings.database_url.get_secret_value())
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Subscriber.metadata


def run_migrations_offline() -> None:
    getattr(alembic_context, "configure")(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with getattr(alembic_context, "begin_transaction")():
        getattr(alembic_context, "run_migrations")()


def run_sync_migrations(connection) -> None:
    getattr(alembic_context, "configure")(
        connection=connection, target_metadata=target_metadata, compare_type=True
    )
    with getattr(alembic_context, "begin_transaction")():
        getattr(alembic_context, "run_migrations")()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        {"sqlalchemy.url": database_url},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(run_sync_migrations)
    await connectable.dispose()


if getattr(alembic_context, "is_offline_mode")():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())