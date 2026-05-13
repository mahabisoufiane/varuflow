"""Tests for the BankID login endpoints (/api/local-auth/bankid/*).

The BankID backend is mocked via httpx.MockTransport so the test
never touches a real BankID host or a client certificate — we just
assert our own orchestration (order book-keeping, JWT minting,
personnummer hashing, audit trail, replay protection).
"""
from __future__ import annotations

import uuid

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.main import app
from app.config import settings
from app.models.audit import AuditLogEntry
from app.models.auth import AuthRefreshToken, AuthUser
from app.services import bankid
from app.services import auth_service




async def _postgres_ok(db):
    try:
        await db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


class _FakeBankID:
    """Stand-in BankID relying-party API.

    Emits a pending collect the first call so we also exercise the
    QR-refresh path, then completes on the second call with a fixed
    synthetic user.
    """

    def __init__(self, personal_number: str = "198001011234"):
        self.personal_number = personal_number
        self.calls = 0

    def transport(self) -> httpx.MockTransport:
        def handler(req: httpx.Request) -> httpx.Response:
            path = req.url.path
            if path.endswith("/auth"):
                return httpx.Response(200, json={
                    "orderRef": "order-ref-123",
                    "autoStartToken": "auto-start-token-abc",
                    "qrStartToken": "qr-start-token-xyz",
                    "qrStartSecret": "00112233445566778899aabbccddeeff",
                })
            if path.endswith("/collect"):
                self.calls += 1
                if self.calls == 1:
                    return httpx.Response(200, json={
                        "orderRef": "order-ref-123",
                        "status": "pending",
                        "hintCode": "outstandingTransaction",
                    })
                return httpx.Response(200, json={
                    "orderRef": "order-ref-123",
                    "status": "complete",
                    "completionData": {
                        "user": {
                            "personalNumber": self.personal_number,
                            "name": "Test Testsson",
                            "givenName": "Test",
                            "surname": "Testsson",
                        },
                    },
                })
            return httpx.Response(404)
        return httpx.MockTransport(handler)


@pytest_asyncio.fixture
async def bankid_env(db_session, monkeypatch):
    """Patch settings + bankid._client to route every call at a mocked API."""
    if not await _postgres_ok(db_session):
        pytest.skip("PostgreSQL not reachable")
    monkeypatch.setattr(settings, "BANKID_CLIENT_CERT_PATH", "/fake/cert.pem")
    monkeypatch.setattr(settings, "BANKID_CA_CERT_PATH", "")
    fake = _FakeBankID()

    def _fake_client():
        return httpx.AsyncClient(
            base_url=settings.BANKID_API_URL,
            transport=fake.transport(),
            headers={"Content-Type": "application/json"},
        )

    monkeypatch.setattr(bankid, "_client", _fake_client)
    return fake


async def test_bankid_init_returns_order_and_qr(bankid_env, db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/local-auth/bankid/init", json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["order_ref"] == "order-ref-123"
    assert body["auto_start_token"] == "auto-start-token-abc"
    assert body["qr_data"].startswith("bankid.qr-start-token-xyz.")
    parts = body["qr_data"].split(".")
    # bankid.<token>.<time>.<hmac> → 4 parts
    assert len(parts) == 4
    assert len(parts[3]) == 64  # sha-256 hex


async def test_bankid_collect_pending_then_complete_mints_jwt(bankid_env, db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        init = (await c.post("/api/local-auth/bankid/init", json={})).json()
        order_ref = init["order_ref"]

        # First poll — pending, carries a refreshed QR frame.
        pending = await c.get(f"/api/local-auth/bankid/collect?orderRef={order_ref}")
        assert pending.status_code == 200
        p = pending.json()
        assert p["status"] == "pending"
        assert p["qr_data"] is not None

        # Second poll — complete, issues tokens.
        done = await c.get(f"/api/local-auth/bankid/collect?orderRef={order_ref}")
        assert done.status_code == 200, done.text
        d = done.json()
        assert d["status"] == "complete"
        assert d["access_token"]
        assert d["refresh_token"]

    # JWT should decode under the same secret as the password flow.
    payload = auth_service.decode_access_token(d["access_token"])
    assert payload["type"] == "access"
    user_id = uuid.UUID(payload["sub"])
    user = await db_session.get(AuthUser, user_id)
    assert user is not None
    assert user.is_email_verified is True
    # Personnummer stored as SHA-256 of "198001011234"
    assert user.personalnummer_hash == bankid.hash_personnummer("198001011234")

    # Refresh token row persisted
    rt_rows = (await db_session.execute(
        select(AuthRefreshToken).where(AuthRefreshToken.user_id == user.id)
    )).scalars().all()
    assert len(rt_rows) == 1
    assert rt_rows[0].revoked is False

    # Audit entry written
    audits = (await db_session.execute(
        select(AuditLogEntry).where(
            AuditLogEntry.action == "BANKID_LOGIN",
            AuditLogEntry.target_id == str(user.id),
        )
    )).scalars().all()
    assert len(audits) == 1
    assert audits[0].extra.get("new_user") is True
    assert audits[0].extra.get("given_name") == "Test"

    # Cleanup: refresh the test's copy to avoid FK cascade surprises in
    # other tests that share the same DB session.
    await db_session.delete(user)
    await db_session.commit()


async def test_bankid_collect_replay_rejected(bankid_env, db_session):
    """A second collect on the same orderRef after success must 409."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        init = (await c.post("/api/local-auth/bankid/init", json={})).json()
        order_ref = init["order_ref"]
        await c.get(f"/api/local-auth/bankid/collect?orderRef={order_ref}")  # pending
        first = await c.get(f"/api/local-auth/bankid/collect?orderRef={order_ref}")
        assert first.status_code == 200
        second = await c.get(f"/api/local-auth/bankid/collect?orderRef={order_ref}")
    assert second.status_code == 409

    # Cleanup the account created in the successful collect so this test
    # stays idempotent when re-run.
    payload = auth_service.decode_access_token(first.json()["access_token"])
    user = await db_session.get(AuthUser, uuid.UUID(payload["sub"]))
    if user:
        await db_session.delete(user)
        await db_session.commit()


async def test_bankid_init_returns_503_when_not_configured(db_session, monkeypatch):
    monkeypatch.setattr(settings, "BANKID_CLIENT_CERT_PATH", "")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/local-auth/bankid/init", json={})
    assert r.status_code == 503
