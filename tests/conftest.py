import os

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Tests run against a DEDICATED test database on the compose Postgres, never the
# app database — the fixture does drop_all on teardown, so isolation is mandatory.
TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://agent:agent@localhost:5432/email_agent_test",
)


@pytest_asyncio.fixture
async def session():
    from email_agent.db import Base
    from email_agent import state  # noqa: F401 (registers models)

    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
