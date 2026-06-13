from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import Select

from app.config import settings

# Convert postgresql:// to postgresql+asyncpg:// so SQLAlchemy uses the
# async asyncpg driver instead of the synchronous psycopg2 driver.
db_url = settings.DATABASE_URL
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(
    db_url,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,       # reconnect dropped connections
    pool_recycle=1800,        # recycle connections every 30 min
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session


def scoped_select(model_class: type, org_id: uuid.UUID) -> Select:
    """Return a SELECT already filtered by org_id.

    Use this instead of bare select() for any query on tenant-owned data.
    Forgetting org_id is a tenant isolation bug — this helper makes the
    correct pattern the ergonomic default.

    Example:
        q = scoped_select(Product, org_id).where(Product.is_active == True)
        result = await db.execute(q)

    For queries that must NOT filter by org_id (e.g. public endpoints,
    admin operations) use select() directly and add a comment explaining why.
    """
    return select(model_class).where(model_class.org_id == org_id)
