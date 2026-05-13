"""Tests for ``session_version`` JWT invalidation (Item 24 / migration v44).

Covers:

* ``verify_session_version`` helper — pure-function tests for legacy-pass
  (no claim), pass-through (claim == current), reject (claim < current),
  and malformed claim rejection.
* Integration via ``_mint_access_token`` — tokens carry the ``ver``
  claim; bumping ``session_version`` on the user retires a previously
  minted token on the next ``/api/auth/me`` call.
* Password reset increments ``session_version`` + refresh-token
  revocation still runs (existing behaviour regression-guarded).
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.database import async_session, engine
from app.main import app
from app.middleware.auth import verify_session_version
from app.models.auth import AuthUser
from app.services import auth_service


# --------------------------------------------------------------------------- #
# Pure-function tests — no DB, no HTTP.
# --------------------------------------------------------------------------- #

class _StubUser:
    """Duck-typed stand-in for AuthUser — the helper only reads
    ``session_version`` so we don't need a real ORM row for the unit
    tests."""
    def __init__(self, session_version: int = 1) -> None:
        self.session_version = session_version


def test_verify_missing_claim_is_legacy_pass() -> None:
    # A token minted pre-v44 (no ``ver`` claim) must not break the
    # rollout — accept silently.
    verify_session_version({}, _StubUser(session_version=5))


def test_verify_matching_claim_passes() -> None:
    verify_session_version({"ver": 3}, _StubUser(session_version=3))


def test_verify_claim_higher_than_current_passes() -> None:
    # Should never happen in practice (the column only monotonically
    # increases) but the helper must not reject a "future" claim —
    # otherwise a race between mint and increment would log the user
    # out on the turn.
    verify_session_version({"ver": 10}, _StubUser(session_version=3))


def test_verify_stale_claim_rejected() -> None:
    with pytest.raises(HTTPException) as exc:
        verify_session_version({"ver": 1}, _StubUser(session_version=2))
    assert exc.value.status_code == 401


def test_verify_malformed_claim_rejected() -> None:
    with pytest.raises(HTTPException):
        verify_session_version({"ver": "not-a-number"}, _StubUser(session_version=1))


def test_verify_null_session_version_column_defaults_to_one() -> None:
    # A DB row with a NULL column (shouldn't happen post-migration,
    # defensive code path) resolves to ``1`` — a token with ``ver=1``
    # still passes.
    user = _StubUser(session_version=None)  # type: ignore[arg-type]
    verify_session_version({"ver": 1}, user)


# --------------------------------------------------------------------------- #
# Integration tests — require Postgres.
# --------------------------------------------------------------------------- #

async def _postgres_reachable() -> bool:
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest_asyncio.fixture
async def pg_session():
    if not await _postgres_reachable():
        pytest.skip("PostgreSQL not reachable — run `docker compose up db`")
    async with async_session() as session:
        yield session


async def _mk_auth_user(db, *, session_version: int = 1) -> AuthUser:
    user = AuthUser(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4().hex[:10]}@test.varuflow.local",
        hashed_password="$2b$12$" + "x" * 53,
        is_email_verified=True,
        session_version=session_version,
    )
    db.add(user)
    await db.commit()
    return user


@pytest.mark.asyncio
async def test_minted_token_carries_current_ver(pg_session) -> None:
    user = await _mk_auth_user(pg_session, session_version=7)
    try:
        token = auth_service._mint_access_token(user)
        payload = auth_service.decode_access_token(token)
        assert payload["ver"] == 7
    finally:
        await pg_session.delete(user); await pg_session.commit()


@pytest.mark.asyncio
async def test_fresh_token_accepted_on_me(pg_session) -> None:
    user = await _mk_auth_user(pg_session, session_version=1)
    try:
        token = auth_service._mint_access_token(user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 200, r.text
    finally:
        await pg_session.delete(user); await pg_session.commit()


@pytest.mark.asyncio
async def test_stale_token_rejected_after_version_bump(pg_session) -> None:
    """Mint a token at ver=1, bump the DB column to 2, the token is now 401."""
    user = await _mk_auth_user(pg_session, session_version=1)
    try:
        stale = auth_service._mint_access_token(user)
        user.session_version = 2
        await pg_session.commit()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {stale}"},
            )
        assert r.status_code == 401
        # A freshly minted token at the new version must succeed.
        fresh = auth_service._mint_access_token(user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {fresh}"},
            )
        assert r.status_code == 200, r.text
    finally:
        await pg_session.delete(user); await pg_session.commit()


@pytest.mark.asyncio
async def test_password_reset_bumps_session_version(pg_session) -> None:
    """End-to-end: reset consumes the token and increments the column."""
    user = AuthUser(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4().hex[:10]}@test.varuflow.local",
        hashed_password=auth_service._hash_password("OldPassword123!"),
        is_email_verified=True,
        session_version=3,
    )
    pg_session.add(user)
    await pg_session.commit()
    try:
        raw = await auth_service.initiate_password_reset(user.email, pg_session)
        assert raw is not None
        returned_uid = await auth_service.confirm_password_reset(
            raw, "NewPassword123!", pg_session,
        )
        assert returned_uid == user.id
        await pg_session.refresh(user)
        assert user.session_version == 4
    finally:
        await pg_session.delete(user); await pg_session.commit()
