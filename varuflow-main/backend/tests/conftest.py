"""Shared test fixtures.

These tests need a real PostgreSQL instance because the models use
Postgres-specific types (UUID, ENUM). In CI this is provided by the
`postgres` service in .github/workflows/ci.yml; locally either run
`docker compose up db` or skip the Postgres-bound tests with
`pytest -m "not postgres"`.

Fixtures:
  `db_session`    — fresh AsyncSession bound to the configured database
  `client_factory`— builds an httpx AsyncClient whose `get_current_member`
                    dependency is overridden to return a given member row.
"""
from __future__ import annotations

import os
# Force development mode so the production-config validator in app.main's
# lifespan does not abort the TestClient startup. Must run before importing
# app.main / app.config.
os.environ.setdefault("ENV", "development")
# Provide a placeholder DATABASE_URL so alembic env.py can import. Tests that
# actually need Postgres skip themselves when the engine can't connect.
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://test:test@127.0.0.1:5432/varuflow_test"
)

import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session, engine
from app.main import app
from app.middleware.auth import MemberCtx, get_current_member
from app.middleware.rate_limit import _reset_for_tests as _reset_rate_limit
from app.models.organization import Organization, OrganizationMember, OrgRole


@pytest.fixture(autouse=True)
def _reset_rate_limit_between_tests():
    """Per-path in-memory rate-limit counters leak across tests and cause
    spurious 429s in unrelated suites. Wipe before and after each test."""
    _reset_rate_limit()
    yield
    _reset_rate_limit()


async def _postgres_reachable() -> bool:
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    reachable = await _postgres_reachable()
    if not reachable:
        pytest.skip("PostgreSQL not reachable — run `docker compose up db` or set DATABASE_URL")
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def two_orgs(db_session: AsyncSession):
    """Create two isolated organizations with one owner each."""
    org_a = Organization(id=uuid.uuid4(), name="Alpha AB", org_number="556000-0001")
    org_b = Organization(id=uuid.uuid4(), name="Bravo AB", org_number="556000-0002")

    user_a_id = uuid.uuid4()
    user_b_id = uuid.uuid4()

    member_a = OrganizationMember(org_id=org_a.id, user_id=user_a_id, role=OrgRole.OWNER)
    member_b = OrganizationMember(org_id=org_b.id, user_id=user_b_id, role=OrgRole.OWNER)

    db_session.add_all([org_a, org_b, member_a, member_b])
    await db_session.commit()

    yield {
        "a": {"org": org_a, "user_id": user_a_id, "member": member_a},
        "b": {"org": org_b, "user_id": user_b_id, "member": member_b},
    }

    # Teardown — cascade removes members + any related rows created in tests
    await db_session.delete(org_a)
    await db_session.delete(org_b)
    await db_session.commit()


@pytest.fixture
def client_factory():
    """Return a function that builds an auth-overridden AsyncClient.

    Usage:
        async with client_factory(member) as client:
            await client.get("/api/inventory/products")
    """
    def _build(member: OrganizationMember):
        async def _override():
            user = {"user_id": member.user_id, "email": "test@varuflow.local"}
            return MemberCtx(user, member)

        app.dependency_overrides[get_current_member] = _override
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    yield _build
    app.dependency_overrides.pop(get_current_member, None)
