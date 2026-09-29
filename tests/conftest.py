from collections.abc import AsyncIterator

import asyncpg
import pytest_asyncio
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.infrastructure.database.base import Base


TEST_DATABASE_NAME = "spa_test"


@pytest_asyncio.fixture(scope="session")
async def test_engine() -> AsyncIterator[AsyncEngine]:
    database_url = make_url(settings.database_url)

    admin_url = database_url.set(
        host="localhost",
        port=5433,
        database="postgres",
    )

    admin_connection = await asyncpg.connect(
        host=admin_url.host,
        port=admin_url.port,
        user=admin_url.username,
        password=admin_url.password,
        database=admin_url.database,
    )

    try:
        database_exists = await admin_connection.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1",
            TEST_DATABASE_NAME,
        )

        if not database_exists:
            await admin_connection.execute(
                f'CREATE DATABASE "{TEST_DATABASE_NAME}"'
            )
    finally:
        await admin_connection.close()

    test_url = database_url.set(
        host="localhost",
        port=5433,
        database=TEST_DATABASE_NAME,
    )

    engine = create_async_engine(
        test_url,
        poolclass=NullPool,
    )

    yield engine

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(
    test_engine: AsyncEngine,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    yield async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)