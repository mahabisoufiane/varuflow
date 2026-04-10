# File: migrations/env.py
# Purpose: Alembic async migration runner — reads DATABASE_URL from env, rewrites scheme
# Used by: alembic upgrade head (Railway start command, local dev)

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.models import Base

# ---------------------------------------------------------------------------
# Database URL — read from environment, never from a hardcoded string.
# Supabase (and many PaaS providers) supply postgresql:// without a driver
# suffix. SQLAlchemy 2.x requires postgresql+asyncpg:// for the async driver.
# ---------------------------------------------------------------------------
_raw_url = os.getenv("DATABASE_URL", "")

if not _raw_url:
    raise RuntimeError(
        "DATABASE_URL environment variable is not set. "
        "Add it to Railway Variables: postgresql+asyncpg://USER:PASS@HOST:5432/DBNAME"
    )

if _raw_url.startswith("postgresql://"):
    _raw_url = _raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif _raw_url.startswith("postgres://"):
    # Some Heroku/Railway shortcuts use the 'postgres://' alias
    _raw_url = _raw_url.replace("postgres://", "postgresql+asyncpg://", 1)

DATABASE_URL = _raw_url

# ---------------------------------------------------------------------------
# Alembic config object — gives access to values in alembic.ini
# ---------------------------------------------------------------------------
config = context.config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Offline mode — generate SQL without a live DB connection (for review/CI)
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online mode — connect to the live database and apply migrations
# ---------------------------------------------------------------------------
def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
