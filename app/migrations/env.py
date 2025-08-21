from logging.config import fileConfig
import os

from alembic import context
from sqlalchemy import Connection
from sqlalchemy import MetaData
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.task.models import Task
from app.user.models import User


config = context.config

# Get the raw URL template from the .ini file
raw_db_url = config.get_main_option("sqlalchemy.url")

if raw_db_url is None:
    raise ValueError("The 'sqlalchemy.url' option is not set in your alembic.ini file.")

# Expand the shell-like environment variables in the URL
# This will replace ${POSTGRES_USER} with the actual value, etc.
expanded_db_url = os.path.expandvars(raw_db_url)
config.set_main_option("sqlalchemy.url", expanded_db_url)


if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = MetaData()

User.metadata.tables["users"].to_metadata(target_metadata)
Task.metadata.tables["tasks"].to_metadata(target_metadata)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    section = config.get_section(config.config_ini_section)
    if section is None:
        raise ValueError(
            f"Alembic section '{config.config_ini_section}'"
            f" not found in config file."
        )
    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    def do_migrations(conn: Connection) -> None:
        """Configure the context and run migrations."""
        context.configure(connection=conn, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

    async with connectable.connect() as connection:
        await connection.run_sync(do_migrations)


if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(run_migrations_online())
