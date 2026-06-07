"""Authentication hardening tests.

These tests exercise the rules in CLAUDE.md Rule 2:
  - Unauthenticated requests to internal routes are rejected.
  - Portal JWTs must not be accepted on internal routes.
  - Invalid / unsigned JWTs are rejected when signature enforcement is on.
  - The dev bypass only opens when BOTH ENV=development AND
    ALLOW_DEV_BYPASS=True — a single misconfigured flag is not enough.
"""
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.config import settings
from app.main import app
from app.middleware import auth as auth_module


_TEST_SECRET = "test-secret-at-least-32-characters-long-for-hs256"


def _issue(payload: dict, secret: str = _TEST_SECRET) -> str:
    return jwt.encode(payload, secret, algorithm="HS256")  # nosemgrep: python.jwt.security.audit.jwt-exposed-data.jwt-python-exposed-data


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
def enforce_prod(monkeypatch):
    """Simulate a hardened production config."""
    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "ALLOW_DEV_BYPASS", False)
    monkeypatch.setattr(settings, "ENFORCE_JWT_SIGNATURE", True)
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", _TEST_SECRET)


async def test_missing_token_rejected_in_production(client, enforce_prod):
    async with client as c:
        r = await c.get("/api/inventory/products")
    assert r.status_code == 401


async def test_invalid_signature_rejected(client, enforce_prod):
    bad = _issue(
        {"sub": "00000000-0000-0000-0000-000000000001"},
        secret="wrong-secret-wrong-secret-wrong-secret!!",
    )
    async with client as c:
        r = await c.get(
            "/api/inventory/products",
            headers={"Authorization": f"Bearer {bad}"},
        )
    assert r.status_code == 401


async def test_portal_token_rejected_on_internal_route(client, enforce_prod):
    """A portal-scoped JWT must never authenticate internal API calls."""
    portal_token = _issue(
        {
            "sub": "00000000-0000-0000-0000-000000000001",
            "type": "portal",
            "exp": datetime.now(tz=timezone.utc) + timedelta(hours=1),
        }
    )
    async with client as c:
        r = await c.get(
            "/api/inventory/products",
            headers={"Authorization": f"Bearer {portal_token}"},
        )
    assert r.status_code == 401
    assert "portal" in r.json()["detail"].lower()


async def test_dev_bypass_requires_both_flags(client, monkeypatch):
    """ENV=development alone is not enough — ALLOW_DEV_BYPASS must also be True."""
    monkeypatch.setattr(settings, "ENV", "development")
    monkeypatch.setattr(settings, "ALLOW_DEV_BYPASS", False)
    monkeypatch.setattr(settings, "ENFORCE_JWT_SIGNATURE", True)
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", _TEST_SECRET)

    async with client as c:
        r = await c.get("/api/inventory/products")
    assert r.status_code == 401


async def test_decode_token_refuses_unverified_in_production(monkeypatch):
    """Belt-and-suspenders: even if ENFORCE_JWT_SIGNATURE is flipped off, the
    unverified branch must refuse to run outside ENV=development."""
    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "ENFORCE_JWT_SIGNATURE", False)
    from jose import JWTError

    with pytest.raises(JWTError):
        auth_module._decode_token(_issue({"sub": "anything"}))
