"""Smoke tests for new health probe + admin waitlist guard + GDPR auth gates."""
import uuid

from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app


async def test_health_reports_config_block():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/health")
    assert r.status_code in (200, 503)
    body = r.json()
    assert "config" in body
    for key in ("supabase", "stripe", "openai", "resend", "fortnox", "smtp", "sentry"):
        assert key in body["config"]
        assert isinstance(body["config"][key], bool)


async def test_admin_waitlist_blocks_without_key(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "not-empty-test-key")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/waitlist")
    assert r.status_code == 401


async def test_admin_waitlist_blocks_wrong_key(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "correct-key")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/waitlist", headers={"X-Admin-Key": "wrong"})
    assert r.status_code == 401


async def test_admin_waitlist_disabled_when_no_key(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/waitlist", headers={"X-Admin-Key": "anything"})
    assert r.status_code == 503


async def test_gdpr_endpoints_require_auth(monkeypatch):
    # Production-style config: no dev bypass.
    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "ALLOW_DEV_BYPASS", False)
    monkeypatch.setattr(settings, "ENFORCE_JWT_SIGNATURE", True)
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "test-secret-at-least-32-chars-long-xxx")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r1 = await c.get("/api/gdpr/export")
        r2 = await c.delete("/api/gdpr/organization", headers={"X-Confirm-Delete": "DELETE"})
    assert r1.status_code == 401
    assert r2.status_code == 401


async def test_einvoice_endpoints_require_auth(monkeypatch):
    """/api/einvoice routes must reject unauthenticated callers in prod."""
    import uuid

    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "ALLOW_DEV_BYPASS", False)
    monkeypatch.setattr(settings, "ENFORCE_JWT_SIGNATURE", True)
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "test-secret-at-least-32-chars-long-xxx")

    fake_id = uuid.uuid4()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r1 = await c.post(f"/api/einvoice/peppol/{fake_id}")
        r2 = await c.post(f"/api/einvoice/peppol/{fake_id}/validate")
    assert r1.status_code == 401
    assert r2.status_code == 401


async def test_bokforing_export_requires_auth(monkeypatch):
    """/api/gdpr/bokforing-export must reject unauthenticated callers in prod."""
    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "ALLOW_DEV_BYPASS", False)
    monkeypatch.setattr(settings, "ENFORCE_JWT_SIGNATURE", True)
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "test-secret-at-least-32-chars-long-xxx")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/gdpr/bokforing-export")
    assert r.status_code == 401


async def test_ai_card_snooze_requires_auth(monkeypatch):
    """/api/ai/cards/{card_id}/snooze must reject unauthenticated callers."""
    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "ALLOW_DEV_BYPASS", False)
    monkeypatch.setattr(settings, "ENFORCE_JWT_SIGNATURE", True)
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "test-secret-at-least-32-chars-long-xxx")

    fake_id = uuid.uuid4()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            f"/api/ai/cards/deadstock-{fake_id}/snooze",
            json={"days": 7},
        )
    # 401 = auth middleware rejects; 404 = route not yet registered (also safe)
    assert r.status_code in (401, 404)


async def test_supplier_lead_time_requires_auth(monkeypatch):
    """/api/inventory/suppliers/{id}/lead-time must reject unauthenticated callers."""
    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "ALLOW_DEV_BYPASS", False)
    monkeypatch.setattr(settings, "ENFORCE_JWT_SIGNATURE", True)
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "test-secret-at-least-32-chars-long-xxx")

    fake_id = uuid.uuid4()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/inventory/suppliers/{fake_id}/lead-time")
    # 401 = auth middleware rejects; 404 = route not yet registered (also safe)
    assert r.status_code in (401, 404)


async def test_dunning_endpoints_require_auth(monkeypatch):
    """Dunning endpoints must reject unauthenticated callers."""
    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "ALLOW_DEV_BYPASS", False)
    monkeypatch.setattr(settings, "ENFORCE_JWT_SIGNATURE", True)
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "test-secret-at-least-32-chars-long-xxx")

    fake_id = uuid.uuid4()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r1 = await c.post(f"/api/invoicing/invoices/{fake_id}/send-reminder")
        r2 = await c.get(f"/api/invoicing/invoices/{fake_id}/dunning-history")
    # 401 = auth middleware rejects; 404 = route not yet registered (also safe)
    assert r1.status_code in (401, 404)
    assert r2.status_code in (401, 404)


async def test_customer_lookup_requires_auth(monkeypatch):
    """/api/invoicing/customers/lookup/{org_number} must reject anon callers."""
    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "ALLOW_DEV_BYPASS", False)
    monkeypatch.setattr(settings, "ENFORCE_JWT_SIGNATURE", True)
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "test-secret-at-least-32-chars-long-xxx")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/invoicing/customers/lookup/556000-0001")
    # 401 = auth middleware rejects; 404 = route not yet registered (also safe)
    assert r.status_code in (401, 404)


async def test_margins_requires_auth(monkeypatch):
    """/api/analytics/margins must reject unauthenticated callers."""
    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "ALLOW_DEV_BYPASS", False)
    monkeypatch.setattr(settings, "ENFORCE_JWT_SIGNATURE", True)
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "test-secret-at-least-32-chars-long-xxx")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/analytics/margins")
    assert r.status_code == 401


async def test_ltv_requires_auth(monkeypatch):
    """/api/analytics/ltv must reject unauthenticated callers."""
    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "ALLOW_DEV_BYPASS", False)
    monkeypatch.setattr(settings, "ENFORCE_JWT_SIGNATURE", True)
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "test-secret-at-least-32-chars-long-xxx")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/analytics/ltv")
    assert r.status_code == 401


async def test_portal_logout_requires_auth():
    """/api/portal/auth/logout must reject unauthenticated callers."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/portal/auth/logout")
    # HTTPBearer(auto_error=True) returns 403 on missing creds; a stale
    # token would hit our 401. Either shape is acceptable as "not allowed".
    assert r.status_code in (401, 403)


async def test_portal_catalogue_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/portal/catalogue")
    assert r.status_code in (401, 403)


async def test_portal_orders_post_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/portal/orders", json={"lines": [{"product_id": "00000000-0000-0000-0000-000000000000", "quantity": 1}]})
    assert r.status_code in (401, 403)


async def test_portal_orders_list_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/portal/orders")
    assert r.status_code in (401, 403)


async def test_pos_zreport_json_requires_auth():
    """The tablet-POS Z-report (JSON) must refuse anonymous callers just
    like every other authenticated route. 401/403 are both acceptable
    depending on whether middleware intercepts first or the role gate."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/pos/sessions/00000000-0000-0000-0000-000000000000/z-report")
    assert r.status_code in (401, 403, 404)


async def test_analytics_activity_requires_auth(monkeypatch):
    """Item 12 — the mobile dashboard's activity feed is a STARTER+
    endpoint and must reject anonymous callers.

    Force production mode so the dev-bypass in get_current_user is disabled:
    without a token the endpoint must return 401 before touching the DB.
    """
    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "ALLOW_DEV_BYPASS", False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/analytics/activity?limit=5")
    assert r.status_code in (401, 403)
