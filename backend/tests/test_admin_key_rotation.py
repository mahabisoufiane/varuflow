"""Tests for admin key rotation (Feature 12).

Verifies:
  * current key grants access
  * previous key grants access AND emits ADMIN_KEY_ROTATION_USED audit
  * an unknown key is rejected
  * once previous is cleared, old key no longer works
  * when neither key is set, admin endpoints return 503
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.config import settings
from app.main import app
from app.models.audit import AuditLogEntry




async def _count_rotation_audits(db) -> int:
    rows = (await db.execute(
        select(AuditLogEntry).where(
            AuditLogEntry.action == "ADMIN_KEY_ROTATION_USED",
        )
    )).scalars().all()
    return len(rows)


async def test_current_admin_key_accepted(monkeypatch, db_session):
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "current-key-xxxxxxxxxxxxxxxxx")
    monkeypatch.setattr(settings, "ADMIN_API_KEY_PREVIOUS", "")
    before = await _count_rotation_audits(db_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(
            "/api/waitlist",
            headers={"X-Admin-Key": "current-key-xxxxxxxxxxxxxxxxx"},
        )
    assert r.status_code == 200

    after = await _count_rotation_audits(db_session)
    assert after == before, "current key must NOT emit a rotation audit row"


async def test_previous_admin_key_accepted_and_audited(monkeypatch, db_session):
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "new-key-xxxxxxxxxxxxxxxxxxxxx")
    monkeypatch.setattr(settings, "ADMIN_API_KEY_PREVIOUS", "old-key-xxxxxxxxxxxxxxxxxxxxx")
    before = await _count_rotation_audits(db_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(
            "/api/waitlist",
            headers={"X-Admin-Key": "old-key-xxxxxxxxxxxxxxxxxxxxx"},
        )
    assert r.status_code == 200

    after = await _count_rotation_audits(db_session)
    assert after == before + 1, "old key must emit ADMIN_KEY_ROTATION_USED audit"


async def test_unknown_admin_key_rejected(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "one-key-xxxxxxxxxxxxxxxxxxxxxxxx")
    monkeypatch.setattr(settings, "ADMIN_API_KEY_PREVIOUS", "other-xxxxxxxxxxxxxxxxxxxxxxxx")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(
            "/api/waitlist",
            headers={"X-Admin-Key": "neither-of-those"},
        )
    assert r.status_code == 401


async def test_previous_cleared_rejects_old_key(monkeypatch):
    """After the rotation window the old key must no longer work."""
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "final-key-xxxxxxxxxxxxxxxxxxxx")
    monkeypatch.setattr(settings, "ADMIN_API_KEY_PREVIOUS", "")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(
            "/api/waitlist",
            headers={"X-Admin-Key": "old-key-xxxxxxxxxxxxxxxxxxxxx"},
        )
    assert r.status_code == 401


async def test_no_keys_configured_returns_503(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "")
    monkeypatch.setattr(settings, "ADMIN_API_KEY_PREVIOUS", "")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(
            "/api/waitlist",
            headers={"X-Admin-Key": "anything"},
        )
    assert r.status_code == 503


async def test_missing_header_rejected(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "current-key-xxxxxxxxxxxxxxxxx")
    monkeypatch.setattr(settings, "ADMIN_API_KEY_PREVIOUS", "")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/waitlist")
    assert r.status_code == 401
