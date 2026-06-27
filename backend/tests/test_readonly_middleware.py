"""Tests for ReadOnlyMiddleware — writes blocked in READONLY_MODE."""
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def test_readonly_blocks_writes(monkeypatch):
    monkeypatch.setattr(settings, "READONLY_MODE", True)
    with TestClient(app) as client:
        res = client.post("/api/team/invite", json={"email": "a@b.c"})
        assert res.status_code == 503
        assert res.json()["code"] == "READONLY_MODE"
        assert res.headers.get("Retry-After") == "300"


def _is_readonly_rejection(res) -> bool:
    if res.status_code != 503:
        return False
    try:
        return res.json().get("code") == "READONLY_MODE"
    except Exception:
        return False


def test_readonly_allows_safe_methods(monkeypatch):
    monkeypatch.setattr(settings, "READONLY_MODE", True)
    with TestClient(app) as client:
        # GET on health is whitelisted anyway but any safe method must pass.
        # Health itself may 503 if DB is unreachable in the test env — we only
        # care that the READONLY middleware did not reject the request.
        res = client.get("/api/health")
        assert not _is_readonly_rejection(res)


def test_readonly_allows_stripe_webhook_even_when_frozen(monkeypatch):
    """Stripe keeps retrying on 5xx — we must stay receptive even in R/O."""
    monkeypatch.setattr(settings, "READONLY_MODE", True)
    with TestClient(app) as client:
        # Webhook will reject on signature, not 503 — that's the whole point.
        res = client.post("/api/billing/webhook", content=b"{}")
        assert not _is_readonly_rejection(res)


def test_readonly_off_by_default():
    """Default must be False — turning writes off in prod without intent is
    catastrophic."""
    # Don't monkeypatch — read the real setting
    from app.config import Settings
    assert Settings.model_fields["READONLY_MODE"].default is False


def test_security_headers_present():
    with TestClient(app) as client:
        res = client.get("/api/health")
        assert res.headers.get("X-Content-Type-Options") == "nosniff"
        assert res.headers.get("X-Frame-Options") == "DENY"
        assert "default-src 'none'" in res.headers.get("Content-Security-Policy", "")
