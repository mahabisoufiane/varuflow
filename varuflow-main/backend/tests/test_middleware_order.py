"""M-8: Middleware order regression guard.

In Starlette, `add_middleware` prepends to `user_middleware` (or the list is
reversed at build time via `reversed()`), so the most recently registered
middleware has the LOWER index and executes FIRST (outermost). The `@app.middleware`
decorator items land at idx 0 and 1; CORSMiddleware at idx 2 is the outermost
of the explicit `add_middleware` calls.

Rule: CORSMiddleware index < any business middleware index → CORS is outermost.

This caught a real outage once (documented in CLAUDE.md rule 1). Keep it.
"""
import pytest
from fastapi.middleware.cors import CORSMiddleware

from app.main import app
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_id import RequestIdMiddleware


def _middleware_index(cls) -> int | None:
    """Return the index of the first Middleware with class ``cls``, or None.

    Lower index = earlier in user_middleware = outermost in execution
    (Starlette reverses the list when building the ASGI chain).
    """
    for i, m in enumerate(app.user_middleware):
        if getattr(m, "cls", None) is cls:
            return i
    return None


def test_cors_middleware_present():
    """CORSMiddleware must be registered in app.user_middleware."""
    types = [m.cls for m in app.user_middleware]
    assert CORSMiddleware in types, (
        "CORSMiddleware missing from app.user_middleware — "
        "it may have been removed or renamed"
    )


def test_cors_is_outer_to_rate_limit():
    """CORSMiddleware must have a lower index than RateLimitMiddleware.

    In Starlette, lower index in user_middleware = registered later = more
    outer (runs first on every request). CORSMiddleware must wrap
    RateLimitMiddleware so that 429 responses include CORS headers.
    """
    cors_idx = _middleware_index(CORSMiddleware)
    rate_idx = _middleware_index(RateLimitMiddleware)

    assert cors_idx is not None, "CORSMiddleware not found in user_middleware"
    assert rate_idx is not None, "RateLimitMiddleware not found in user_middleware"
    assert cors_idx < rate_idx, (
        f"MIDDLEWARE ORDER BUG: CORSMiddleware (idx {cors_idx}) must have a lower "
        f"index than (and therefore be outer to) RateLimitMiddleware (idx {rate_idx}). "
        f"Current user_middleware order: "
        f"{[getattr(m, 'cls', type(m)).__name__ for m in app.user_middleware]}"
    )


def test_cors_is_outer_to_request_id():
    """CORSMiddleware must have a lower index than RequestIdMiddleware.

    Ensures error responses from RequestIdMiddleware carry CORS headers.
    """
    cors_idx = _middleware_index(CORSMiddleware)
    rid_idx = _middleware_index(RequestIdMiddleware)

    assert cors_idx is not None, "CORSMiddleware not found in user_middleware"
    if rid_idx is None:
        pytest.skip("RequestIdMiddleware not in user_middleware — stack shape changed")

    assert cors_idx < rid_idx, (
        f"MIDDLEWARE ORDER BUG: CORSMiddleware (idx {cors_idx}) must be outer than "
        f"RequestIdMiddleware (idx {rid_idx}). "
        f"Order: {[getattr(m, 'cls', type(m)).__name__ for m in app.user_middleware]}"
    )
