from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import engine


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """A real Postgres-backed session (see freshbrain-ai-engine-db's
    docker-compose.yml), wrapped in a transaction that's rolled back after
    each test. join_transaction_mode="create_savepoint" lets code under
    test call session.commit() without escaping this outer transaction —
    commits release/recreate a SAVEPOINT instead."""
    async with engine.connect() as conn:
        await conn.begin()
        session_factory = async_sessionmaker(
            bind=conn,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        session = session_factory()
        try:
            yield session
        finally:
            await session.close()
            await conn.rollback()
