from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
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
    pool_timeout=30,          # raise after 30 s waiting for a connection
    connect_args={"command_timeout": 60},  # per-statement timeout (asyncpg)
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class SoftDeleteMixin:
    """Adds soft-delete to any ORM model.

    Usage: class MyModel(SoftDeleteMixin, Base): ...
    NULL deleted_at = active row. Set via .soft_delete(); filter with .is_deleted.
    Router-level filtering (exclude deleted rows by default) is opt-in per endpoint.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        self.deleted_at = datetime.now(UTC)


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
