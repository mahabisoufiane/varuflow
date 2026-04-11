"""IP-based in-memory rate limiter middleware.

Limit: 100 requests / 60 seconds per IP address.
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
from typing import DefaultDict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

log = logging.getLogger(__name__)

_WINDOW_SECONDS = 60
_MAX_REQUESTS = 100

# {ip: [(timestamp, ...), ...]}  — deque would be cleaner but list is fine at this scale
_counters: DefaultDict[str, list[float]] = defaultdict(list)
_lock = asyncio.Lock()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        ip = _client_ip(request)
        now = time.monotonic()
        window_start = now - _WINDOW_SECONDS

        async with _lock:
            timestamps = _counters[ip]
            # Evict entries outside the window
            _counters[ip] = [t for t in timestamps if t > window_start]
            count = len(_counters[ip])

            if count >= _MAX_REQUESTS:
                log.warning(
                    "Rate limit exceeded | ip=%s | count=%d | path=%s",
                    ip, count, request.url.path,
                )
                retry_after = int(_WINDOW_SECONDS - (now - _counters[ip][0])) + 1
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please slow down."},
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(_MAX_REQUESTS),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(time.time()) + retry_after),
                    },
                )

            _counters[ip].append(now)
            remaining = _MAX_REQUESTS - count - 1

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(_MAX_REQUESTS)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
