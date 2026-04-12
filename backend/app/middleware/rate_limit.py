"""IP-based in-memory rate limiter middleware.

Global limit: 100 requests / 60 seconds per IP address.
Auth endpoints have tighter per-path limits (see _PATH_LIMITS below).

Uses a sliding-window counter backed by a thread-safe defaultdict.
Works for single-instance deployments; swap the counter for Redis
(e.g. redis-py asyncio) when running multiple replicas.

Usage (in main.py):
    from app.middleware.rate_limit import RateLimitMiddleware
    app.add_middleware(RateLimitMiddleware)
"""
import asyncio
import logging
import time
from collections import defaultdict
from typing import NamedTuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings

log = logging.getLogger(__name__)

# ── Global defaults ───────────────────────────────────────────────────────────
_WINDOW_SECONDS = 60
_MAX_REQUESTS   = 100


class _Limit(NamedTuple):
    max_requests: int
    window_seconds: int


# ── Per-path overrides ────────────────────────────────────────────────────────
# These paths receive stricter limits regardless of the global setting.
# Matching is prefix-based so /api/auth/login matches the /api/auth/login entry.
# Order matters: first match wins.
_PATH_LIMITS: list[tuple[str, _Limit]] = [
    # Credential endpoints — 5 attempts per minute to slow brute-force
    ("/api/auth/login",           _Limit(max_requests=5,  window_seconds=60)),
    ("/api/auth/signup",          _Limit(max_requests=5,  window_seconds=60)),
    ("/api/local-auth/login",     _Limit(max_requests=5,  window_seconds=60)),
    ("/api/local-auth/signup",    _Limit(max_requests=5,  window_seconds=60)),
    # MFA — 10 attempts per minute
    ("/api/local-auth/mfa",       _Limit(max_requests=10, window_seconds=60)),
    # Password reset — 3 per hour to limit account enumeration + abuse
    ("/api/auth/password",        _Limit(max_requests=3,  window_seconds=3600)),
    ("/api/local-auth/password",  _Limit(max_requests=3,  window_seconds=3600)),
]

# Separate counter namespace per (path_prefix, ip) so auth counters don't
# share state with the global counter.
# Key: (namespace, ip)  Value: list of monotonic timestamps
_counters: defaultdict[tuple[str, str], list[float]] = defaultdict(list)
_lock = asyncio.Lock()


def _client_ip(request: Request) -> str:
    """Return the real client IP.

    X-Forwarded-For is only trusted when TRUST_PROXY=True (i.e. the app is
    behind a known load balancer such as Railway or Render that injects this
    header).  When TRUST_PROXY=False (direct exposure or untrusted proxy) we
    use request.client.host so an attacker cannot spoof an arbitrary IP by
    crafting the header themselves and bypassing rate limits.
    """
    if settings.TRUST_PROXY:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _resolve_limit(path: str) -> tuple[str, _Limit]:
    """Return the (namespace, Limit) that applies to this path."""
    for prefix, limit in _PATH_LIMITS:
        if path == prefix or path.startswith(prefix + "/") or path.startswith(prefix):
            return prefix, limit
    return "__global__", _Limit(max_requests=_MAX_REQUESTS, window_seconds=_WINDOW_SECONDS)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        ip   = _client_ip(request)
        path = request.url.path
        now  = time.monotonic()

        namespace, limit = _resolve_limit(path)
        window_start = now - limit.window_seconds
        key = (namespace, ip)

        async with _lock:
            # Evict entries outside the window
            _counters[key] = [t for t in _counters[key] if t > window_start]
            count = len(_counters[key])

            if count >= limit.max_requests:
                log.warning(
                    "Rate limit exceeded | ip=%s | path=%s | namespace=%s | count=%d",
                    ip, path, namespace, count,
                )
                oldest       = _counters[key][0]
                retry_after  = int(limit.window_seconds - (now - oldest)) + 1
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please slow down."},
                    headers={
                        "Retry-After":          str(retry_after),
                        "X-RateLimit-Limit":    str(limit.max_requests),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset":    str(int(time.time()) + retry_after),
                    },
                )

            _counters[key].append(now)
            remaining = limit.max_requests - count - 1

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"]     = str(limit.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
