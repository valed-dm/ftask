import asyncio
from typing import AsyncGenerator

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import create_async_engine
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="function")
def db_url(postgres_container: PostgresContainer) -> str:
    """
    Provides the dynamic, async-compatible URL for the test database.
    This is the single source of truth for the database URL.
    """
    raw_url: str = postgres_container.get_connection_url()
    return raw_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")


@pytest.fixture(scope="function")
async def migration_engine(db_url: str) -> AsyncGenerator[AsyncEngine, None]:
    """
    Creates a new async engine for MIGRATION TESTS ONLY.
    It does NOT create any tables, leaving that to Alembic.
    """
    engine = create_async_engine(db_url)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="function")
def alembic_config(db_url: str) -> Config:
    """
    Creates a correctly configured Alembic Config object that points
    to the dynamic, containerized test database.
    """
    config = Config("alembic.ini")
    # Set the sqlalchemy.url to the dynamic URL from db_url fixture.
    config.set_main_option("sqlalchemy.url", db_url)
    return config


async def table_exists(engine: AsyncEngine, table_name: str) -> bool:
    """Async helper to check if a table exists."""
    async with engine.connect() as conn:

        def check_table(sync_conn):
            inspector = inspect(sync_conn)
            return table_name in inspector.get_table_names()

        return await conn.run_sync(check_table)


async def test_migrations_upgrade_downgrade(
    alembic_config: Config, migration_engine: AsyncEngine
) -> None:
    """Ensure Alembic migrations apply and rollback correctly."""
    loop = asyncio.get_running_loop()

    # --- Upgrade to head ---
    # Run the synchronous alembic command in a thread pool executor
    await loop.run_in_executor(None, command.upgrade, alembic_config, "head")

    # Check that both tables now exist in the SAME database
    assert await table_exists(migration_engine, "users")
    assert await table_exists(migration_engine, "tasks")

    # --- Downgrade back to base ---
    await loop.run_in_executor(None, command.downgrade, alembic_config, "base")

    # Now both should be gone
    assert not await table_exists(migration_engine, "users")
    assert not await table_exists(migration_engine, "tasks")


# This test must also be marked as async
async def test_each_migration_step(
    alembic_config: Config, migration_engine: AsyncEngine
) -> None:
    """Ensure each revision creates expected tables."""
    loop = asyncio.get_running_loop()

    # --- Go to base (start clean) ---
    await loop.run_in_executor(None, command.downgrade, alembic_config, "base")

    # --- Upgrade to the first migration ---
    await loop.run_in_executor(None, command.upgrade, alembic_config, "54000a27abfd")
    assert await table_exists(migration_engine, "users")
    assert not await table_exists(migration_engine, "tasks")

    # --- Upgrade to the second migration ---
    await loop.run_in_executor(None, command.upgrade, alembic_config, "31659d68e660")
    assert await table_exists(migration_engine, "tasks")
