"""Rate-limit tests (Item 29).

These tests exercise the middleware + dep-style limiters in isolation
against a minimal FastAPI app — no Postgres, no project conftest. The
repo convention is ``backend/tests/test_*.py`` (see spec note: the
original item referenced ``backend/app/tests/``; we follow the existing
convention so pytest discovery stays unchanged).

Coverage:
  • Middleware admits up to the cap and returns 200 with counting-down
    X-RateLimit-Remaining headers.
  • Middleware returns 429 + Retry-After + X-RateLimit-Reset on the
    first over-cap request.
  • Two IPs do not share a bucket.
  • ``RATE_LIMIT_DISABLED=true`` short-circuits enforcement.
  • Webhook paths are bypassed entirely.
  • ``per_ip_rate_limit`` dep raises 429 after the cap is reached, and
    recovers on window reset (time mocked).
  • ``per_org_rate_limit`` dep scopes buckets per-org (two orgs don't
    share a quota).

These tests do NOT hit the real local_auth/billing/AI routers because
those require Postgres + auth fixtures that live in conftest.py. The
limiter behaviour they depend on is fully covered here.
"""
from __future__ import annotations

import time
from typing import Iterator

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.config import settings
from app.middleware import rate_limit as rl
from app.middleware.rate_limit import (
    RateLimitMiddleware,
    _PATH_LIMITS,
    _reset_for_tests,
    per_ip_rate_limit,
)


@pytest.fixture(autouse=True)
def _fresh_counters() -> Iterator[None]:
    """Clear the shared counter dict before and after every test."""
    _reset_for_tests()
    yield
    _reset_for_tests()


@pytest.fixture
def _enable_limiting(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure RATE_LIMIT_DISABLED is False for the default test cases."""
    monkeypatch.setattr(settings, "RATE_LIMIT_DISABLED", False, raising=False)
    monkeypatch.setattr(settings, "TRUST_PROXY", True, raising=False)


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.get("/api/local-auth/login")
    def login():
        return {"ok": True}

    @app.get("/api/local-auth/whatever")
    def other():
        return {"ok": True}

    @app.get("/api/billing/webhook")
    def webhook():
        return {"ok": True}

    return app


# ── Middleware behaviour ─────────────────────────────────────────────────────

def test_middleware_admits_up_to_cap_and_decrements_remaining(_enable_limiting):
    app = _make_app()
    # /api/local-auth/login is capped at 5/min per IP.
    cap = next(
        lim.max_requests for p, lim in _PATH_LIMITS if p == "/api/local-auth/login"
    )
    with TestClient(app) as c:
        for i in range(cap):
            r = c.get(
                "/api/local-auth/login",
                headers={"X-Forwarded-For": "203.0.113.1"},
            )
            assert r.status_code == 200, r.text
            # Remaining counts down from cap-1 to 0.
            assert r.headers["X-RateLimit-Limit"] == str(cap)
            assert int(r.headers["X-RateLimit-Remaining"]) == cap - 1 - i
            assert int(r.headers["X-RateLimit-Window"]) > 0


def test_middleware_returns_429_with_reset_header_on_over_cap(_enable_limiting):
    app = _make_app()
    cap = next(
        lim.max_requests for p, lim in _PATH_LIMITS if p == "/api/local-auth/login"
    )
    with TestClient(app) as c:
        for _ in range(cap):
            c.get("/api/local-auth/login", headers={"X-Forwarded-For": "203.0.113.2"})
        r = c.get("/api/local-auth/login", headers={"X-Forwarded-For": "203.0.113.2"})
        assert r.status_code == 429
        body = r.json()
        assert "Too many requests" in body["detail"]
        # Every RateLimit-* header present so clients can implement backoff.
        assert int(r.headers["Retry-After"]) >= 1
        assert int(r.headers["X-RateLimit-Limit"]) == cap
        assert r.headers["X-RateLimit-Remaining"] == "0"
        assert int(r.headers["X-RateLimit-Reset"]) >= int(time.time())
        assert int(r.headers["X-RateLimit-Window"]) > 0


def test_middleware_buckets_per_ip(_enable_limiting):
    """Two distinct IPs exhaust their own buckets independently."""
    app = _make_app()
    cap = next(
        lim.max_requests for p, lim in _PATH_LIMITS if p == "/api/local-auth/login"
    )
    with TestClient(app) as c:
        for _ in range(cap):
            c.get("/api/local-auth/login", headers={"X-Forwarded-For": "198.51.100.10"})
        # First IP is exhausted — 429.
        r1 = c.get("/api/local-auth/login", headers={"X-Forwarded-For": "198.51.100.10"})
        assert r1.status_code == 429
        # Second IP is fresh — 200.
        r2 = c.get("/api/local-auth/login", headers={"X-Forwarded-For": "198.51.100.20"})
        assert r2.status_code == 200


def test_middleware_disabled_flag_short_circuits(monkeypatch: pytest.MonkeyPatch):
    """RATE_LIMIT_DISABLED=true admits all requests regardless of cap."""
    monkeypatch.setattr(settings, "RATE_LIMIT_DISABLED", True, raising=False)
    monkeypatch.setattr(settings, "TRUST_PROXY", True, raising=False)
    app = _make_app()
    cap = next(
        lim.max_requests for p, lim in _PATH_LIMITS if p == "/api/local-auth/login"
    )
    with TestClient(app) as c:
        for _ in range(cap * 3):
            r = c.get("/api/local-auth/login", headers={"X-Forwarded-For": "203.0.113.3"})
            assert r.status_code == 200


def test_webhook_paths_bypass_limiting(_enable_limiting):
    """Stripe webhook must never receive a 429 — bypass guaranteed."""
    app = _make_app()
    with TestClient(app) as c:
        # Drive far above the global 100/min cap.
        for _ in range(150):
            r = c.get("/api/billing/webhook", headers={"X-Forwarded-For": "203.0.113.4"})
            assert r.status_code == 200


def test_path_match_is_strict_prefix(_enable_limiting):
    """/api/local-auth/whatever must NOT pick up the /login 5-per-min cap."""
    app = _make_app()
    with TestClient(app) as c:
        # More than the login cap (5) but under the global cap (100).
        for _ in range(20):
            r = c.get(
                "/api/local-auth/whatever",
                headers={"X-Forwarded-For": "203.0.113.5"},
            )
            assert r.status_code == 200


# ── per_ip_rate_limit dep ────────────────────────────────────────────────────

def test_per_ip_dep_locks_out_after_cap_and_recovers(_enable_limiting, monkeypatch):
    """The dep emits 429 at the cap and admits again once the window advances."""
    dep = per_ip_rate_limit("test_bucket", max_requests=3, window_seconds=30)
    app = FastAPI()

    @app.get("/guarded", dependencies=[Depends(dep)])
    def guarded():
        return {"ok": True}

    with TestClient(app) as c:
        # Three hits: all 200.
        for _ in range(3):
            assert c.get("/guarded", headers={"X-Forwarded-For": "192.0.2.10"}).status_code == 200
        # Fourth: 429 with full RateLimit-* header set.
        r = c.get("/guarded", headers={"X-Forwarded-For": "192.0.2.10"})
        assert r.status_code == 429
        assert int(r.headers["Retry-After"]) >= 1
        assert int(r.headers["X-RateLimit-Limit"]) == 3
        assert r.headers["X-RateLimit-Remaining"] == "0"

    # Recovery: advance monotonic time past the window by monkeypatching
    # time.monotonic inside the module, then a fresh hit admits again.
    base = rl.time.monotonic()
    monkeypatch.setattr(rl.time, "monotonic", lambda: base + 60.0)
    with TestClient(app) as c:
        r = c.get("/guarded", headers={"X-Forwarded-For": "192.0.2.10"})
        assert r.status_code == 200, r.text


def test_per_ip_dep_different_buckets_dont_collide(_enable_limiting):
    """Two dep instances with different bucket names have independent counters."""
    a = per_ip_rate_limit("bucket_a", max_requests=2, window_seconds=60)
    b = per_ip_rate_limit("bucket_b", max_requests=2, window_seconds=60)
    app = FastAPI()

    @app.get("/a", dependencies=[Depends(a)])
    def route_a(): return {"ok": True}

    @app.get("/b", dependencies=[Depends(b)])
    def route_b(): return {"ok": True}

    with TestClient(app) as c:
        # Exhaust bucket_a.
        c.get("/a", headers={"X-Forwarded-For": "192.0.2.20"})
        c.get("/a", headers={"X-Forwarded-For": "192.0.2.20"})
        assert c.get("/a", headers={"X-Forwarded-For": "192.0.2.20"}).status_code == 429
        # bucket_b is untouched.
        assert c.get("/b", headers={"X-Forwarded-For": "192.0.2.20"}).status_code == 200


# ── per_org_rate_limit dep ───────────────────────────────────────────────────
#
# The dep-style per-org limiter resolves Depends(get_current_member) from
# app.middleware.auth, which transitively imports ORM models that use
# PEP-604 unions (`str | None`). On Python 3.10+ that loads cleanly; on
# 3.9 it raises TypeError at import time, which is unrelated to the
# limiter logic. The two tests below cover the per-org KEY SHAPE by
# driving the internal _consume() counter directly — the same code path
# the dep uses after resolving the member. A full HTTP-level test that
# also exercises Depends(get_current_member) lives in the authenticated
# integration suite (conftest-based) which already requires 3.10+.

def test_per_org_counter_scopes_by_org_id(_enable_limiting):
    """Two orgs on the same bucket name have independent counters."""
    import asyncio
    import uuid
    from app.middleware.rate_limit import _consume, _Limit

    org_a, org_b = str(uuid.uuid4()), str(uuid.uuid4())
    limit = _Limit(max_requests=2, window_seconds=60)

    async def drive():
        # Exhaust org A: two admits, third is blocked.
        r1 = await _consume(("__org__:test", org_a), limit)
        r2 = await _consume(("__org__:test", org_a), limit)
        r3 = await _consume(("__org__:test", org_a), limit)
        assert r1[1] is None and r2[1] is None
        assert r3[1] is not None, "org A should be capped on the 3rd hit"
        # Org B starts fresh.
        r4 = await _consume(("__org__:test", org_b), limit)
        assert r4[1] is None, "org B must not share org A's counter"

    asyncio.get_event_loop().run_until_complete(drive()) if False else asyncio.run(drive())


def test_per_org_counter_different_buckets_independent(_enable_limiting):
    """A single org with two different bucket names keeps two separate counters."""
    import asyncio
    import uuid
    from app.middleware.rate_limit import _consume, _Limit

    org_id = str(uuid.uuid4())
    limit = _Limit(max_requests=1, window_seconds=60)

    async def drive():
        a = await _consume(("__org__:bucket_a", org_id), limit)
        b = await _consume(("__org__:bucket_b", org_id), limit)
        assert a[1] is None and b[1] is None, "bucket_a and bucket_b must not share state"
        # Second hit on bucket_a is blocked; bucket_b still has its single slot spent already.
        a2 = await _consume(("__org__:bucket_a", org_id), limit)
        assert a2[1] is not None

    asyncio.run(drive())


# ── Router wiring sanity ─────────────────────────────────────────────────────

def test_all_expected_paths_have_tight_caps():
    """Guard against an accidental loosen of a critical limit.

    The values below are the minimum posture Item 29 promises; raising
    them requires updating this assertion AND PROJECT_CONTENTS §58.
    """
    required = {
        "/api/auth/login":                 (5, 60),
        "/api/local-auth/login":           (5, 60),
        "/api/auth/signup":                (5, 60),
        "/api/local-auth/signup":          (5, 60),
        "/api/local-auth/password":        (3, 3600),
        "/api/portal/auth/magic-link":     (3, 3600),
        "/api/gdpr/organization":          (3, 3600),
        "/api/billing/checkout":           (20, 3600),
        "/api/billing/portal":             (20, 3600),
        "/api/eligibility":                (60, 3600),
    }
    found = {p: (lim.max_requests, lim.window_seconds) for p, lim in _PATH_LIMITS}
    for path, (max_req, window) in required.items():
        assert path in found, f"{path} missing from _PATH_LIMITS"
        assert found[path] == (max_req, window), (
            f"{path} posture loosened: got {found[path]}, expected {(max_req, window)}"
        )
