"""Source-contract tests for security headers and middleware ordering.

Verifies that main.py contains the required security headers middleware,
CORS configuration, and rate-limiting middleware by inspecting source code.
No running server or database required.
"""
import inspect
import re

import pytest

from app import main as main_module


@pytest.fixture(scope="module")
def main_source() -> str:
    return inspect.getsource(main_module)


# ── Security header tests ──────────────────────────────────────────────


def test_x_content_type_options_nosniff(main_source: str):
    assert '"X-Content-Type-Options"' in main_source
    assert '"nosniff"' in main_source


def test_x_frame_options_deny(main_source: str):
    assert '"X-Frame-Options"' in main_source
    assert '"DENY"' in main_source


def test_referrer_policy_set(main_source: str):
    assert '"Referrer-Policy"' in main_source
    assert '"strict-origin-when-cross-origin"' in main_source


def test_permissions_policy_set(main_source: str):
    assert '"Permissions-Policy"' in main_source


def test_content_security_policy_set(main_source: str):
    assert '"Content-Security-Policy"' in main_source
    assert "frame-ancestors 'none'" in main_source


# ── CORS tests ─────────────────────────────────────────────────────────


def test_cors_does_not_use_wildcard_origin(main_source: str):
    # allow_origins=["*"] is forbidden per CLAUDE.md Rule 1
    assert 'allow_origins=["*"]' not in main_source


def test_cors_origins_from_env(main_source: str):
    # Must read from settings / env, not hardcoded list
    assert "CORS_ORIGINS" in main_source
    assert re.search(r"allow_origins\s*=\s*settings\.CORS_ORIGINS\.split", main_source)


def test_cors_middleware_is_last_registered(main_source: str):
    """CORSMiddleware must be the last add_middleware call (outermost layer
    in Starlette's LIFO stack)."""
    calls = [
        m.group(1)
        for m in re.finditer(r"app\.add_middleware\(\s*(\w+)", main_source)
    ]
    assert len(calls) >= 2, f"Expected multiple middleware, got {calls}"
    assert calls[-1] == "CORSMiddleware", (
        f"CORSMiddleware must be last add_middleware call, but order is {calls}"
    )


# ── Rate limit middleware ──────────────────────────────────────────────


def test_rate_limit_middleware_registered(main_source: str):
    assert "RateLimitMiddleware" in main_source
    assert re.search(r"app\.add_middleware\(\s*RateLimitMiddleware\s*\)", main_source)


def test_hsts_header_in_production(main_source: str):
    assert '"Strict-Transport-Security"' in main_source
    assert "max-age=" in main_source
