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

# Import the full application so EVERY model is registered on Base.metadata for
# autogenerate. `app.models` alone misses models that are only imported by
# routers/services (e.g. tickets, disputes, share_classes), which would make
# `alembic revision --autogenerate` silently skip them. Importing app.main is a
# no-op for `upgrade`/`downgrade` (those use explicit op.* calls, not metadata).
import app.main  # noqa: E402,F401

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
def _include_object(object_, name, type_, reflected, compare_to):
    # Opt-in additive-only autogenerate (ALEMBIC_ADDITIVE_ONLY=1): emit only
    # ADD operations — new tables, new columns and new indexes present in the
    # models but absent from the DB — never drops or alters. Unset: normal.
    #
    # Type-aware on purpose. The naive form `(not reflected) and (compare_to
    # is None)` also excluded every *existing* (reflected) table, which makes
    # alembic skip diffing their contents entirely — missing COLUMNS on
    # existing tables were silently never detected (that gap is how
    # organizations.fiscal_year_start & co. were missed in 7b5ce99831ed).
    if os.getenv("ALEMBIC_ADDITIVE_ONLY") == "1":
        if type_ == "table":
            # New model table → include; existing pair → include so column
            # diffs run; DB-only table (would be a DROP) → exclude.
            return not (reflected and compare_to is None)
        # Columns/indexes/constraints: only genuinely-new model objects
        # (add_column / create_index). Excluding matched pairs also disables
        # alter_column churn; excluding reflected-only objects disables drops.
        return (not reflected) and (compare_to is None)
    return True


def do_run_migrations(connection: Connection) -> None:
    additive = os.getenv("ALEMBIC_ADDITIVE_ONLY") == "1"
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=_include_object,
        # In additive mode, belt-and-braces: never emit type/default rewrites.
        compare_type=not additive,
        compare_server_default=False,
    )
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
