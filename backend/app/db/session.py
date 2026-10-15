from collections.abc import AsyncIterator

from app.core.config import normalized_database_url, settings
from app.core.worker_runtime import is_workers_runtime

# No Cloudflare Workers (Pyodide) não existe greenlet/aiosqlite utilizáveis e o
# banco é o D1 (app/db/d1.py) — então o SQLAlchemy assíncrono (engine, sessões
# e até o import de sqlalchemy.ext.asyncio) só existe no caminho Docker/Render.
if is_workers_runtime():  # pragma: no cover - apenas no workerd
    engine = None
    SessionLocal = None
else:
    from sqlalchemy.ext.asyncio import (  # pylint: disable=import-outside-toplevel
        async_sessionmaker,
        create_async_engine,
    )

    connect_args = {"ssl": "require"} if settings.database_ssl else {}
    database_url = normalized_database_url(settings.database_url.get_secret_value())
    engine = create_async_engine(
        database_url,
        connect_args=connect_args,
        pool_pre_ping=True,
    )
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator:
    """Sessão SQLAlchemy (Docker/Render) ou None (Workers usam D1)."""
    if SessionLocal is None:  # pragma: no cover - apenas no workerd
        yield None
        return
    async with SessionLocal() as session:
        yield session
