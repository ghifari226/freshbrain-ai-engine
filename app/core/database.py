from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


# Base menjadi induk semua model ORM yang dipetakan ke tabel database.
class Base(DeclarativeBase):
    pass


def sqlalchemy_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


# Engine mengelola pool koneksi, sedangkan session mewakili satu unit kerja database.
engine: AsyncEngine = create_async_engine(
    sqlalchemy_url(get_settings().database_url),
    pool_pre_ping=True,
)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    # Dependency ini memberi satu session per request lalu menutupnya secara otomatis.
    async with SessionFactory() as session:
        yield session


async def dispose_engine() -> None:
    await engine.dispose()
