from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import normalized_database_url, settings

connect_args = {"ssl": "require"} if settings.database_ssl else {}
database_url = normalized_database_url(settings.database_url.get_secret_value())
engine = create_async_engine(
    database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session