"""IP-based rate limiter middleware (Item 29 / C-1 — hardened).

Global limit: 100 requests / 60 seconds per IP address.
Auth, billing, and AI endpoints have tighter per-path limits (see
``_PATH_LIMITS`` below).

In addition to the middleware's per-(path, IP) throttle, this module
exposes two public helpers used as FastAPI dependencies so sensitive
routes can layer on a stricter per-bucket cap (typically per-org or a
long-window per-IP "sustained lockout" on top of the middleware's
burst cap):

    >>> from app.middleware.rate_limit import per_org_rate_limit
    >>> router.post(
    ...     "/checkout",
    ...     dependencies=[Depends(per_org_rate_limit("billing.checkout", 20, 3600))],
    ... )

The bucket is keyed on ``(bucket_name, org_id)`` so a single org cannot
starve the quota of another org sharing an egress IP (SaaS-on-VPN
scenario).

Backend selection (C-1):
  When REDIS_URL is set, a shared Redis sorted-set sliding window is used.
  This counter is shared across all Railway replicas so rate limits are
  enforced correctly regardless of replica count.

  When REDIS_URL is empty (local dev, CI), the implementation falls back
  to the in-memory defaultdict counter — safe for single-process deployments.

Usage (in main.py):
    from app.middleware.rate_limit import RateLimitMiddleware
    app.add_middleware(RateLimitMiddleware)

Test-mode bypass: set ``RATE_LIMIT_DISABLED=true`` in the environment
to short-circuit the middleware AND every dep-style limiter to a
no-op. This is needed so unrelated integration tests that fire many
requests (seed flows, fan-outs) do not false-positive on 429; see
``backend/tests/test_rate_limits.py`` for positive coverage of the
actual limiter logic.
"""
import asyncio
import logging
import time
from collections import defaultdict
from typing import Callable, NamedTuple, Optional, Tuple

from fastapi import Depends, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings

# ── Redis client (C-1) ────────────────────────────────────────────────────────
# Initialised lazily on first use so the module can be imported before the
# event loop exists.  None when REDIS_URL is not configured.
_redis_client = None
_redis_init_attempted = False

# Atomic Lua sliding-window script.
# KEYS[1]  = sorted-set key (namespaced bucket)
# ARGV[1]  = window in seconds
# ARGV[2]  = current wall-clock time in milliseconds (int)
# ARGV[3]  = max requests per window
#
# Returns {remaining, retry_after_ms} where retry_after_ms is -1 on
# admit or the milliseconds until the oldest request leaves the window.
_LUA_SLIDING_WINDOW = """
local key       = KEYS[1]
local window_ms = tonumber(ARGV[1]) * 1000
local now_ms    = tonumber(ARGV[2])
local limit     = tonumber(ARGV[3])

redis.call('ZREMRANGEBYSCORE', key, '-inf', now_ms - window_ms)
local count = tonumber(redis.call('ZCARD', key))
if count >= limit then
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local oldest_ms = tonumber(oldest[2])
    local retry_ms = (oldest_ms + window_ms) - now_ms
    return {0, retry_ms}
end
local member = tostring(now_ms) .. ':' .. tostring(count)
redis.call('ZADD', key, now_ms, member)
redis.call('PEXPIRE', key, window_ms + 1000)
return {limit - count - 1, -1}
"""


async def _get_redis():
    """Return the Redis client, creating it on first call, or None if not configured."""
    global _redis_client, _redis_init_attempted
    if _redis_init_attempted:
        return _redis_client
    _redis_init_attempted = True
    url = getattr(settings, "REDIS_URL", "")
    if not url:
        return None
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(url, decode_responses=False, socket_connect_timeout=2)
        await client.ping()
        _redis_client = client
        log.info("Rate limiter: Redis backend active (%s)", url.split("@")[-1] if "@" in url else url)
    except Exception:
        log.warning("Rate limiter: Redis unavailable — falling back to in-memory counter", exc_info=True)
        _redis_client = None
    return _redis_client

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
#
# Item 29 hardening notes:
#   • Login / signup add a parallel "sustained" lockout via
#     per_ip_rate_limit deps on the router (20/15min for login) so a
#     slow drip that stays under the 5/min burst cap still gets caught.
#   • Billing checkout/portal caps are per-org (via deps) at 20/hour;
#     /api/billing/webhook is Stripe-originated and NOT rate-limited.
#   • /api/eligibility reserved here so a future endpoint inherits the
#     throttle the moment it ships (60/hour per IP).
_PATH_LIMITS: list[tuple[str, _Limit]] = [
    # Credential endpoints — 5 attempts per minute to slow brute-force
    ("/api/auth/login",           _Limit(max_requests=5,  window_seconds=60)),
    ("/api/auth/signup",          _Limit(max_requests=5,  window_seconds=60)),
    ("/api/local-auth/login",     _Limit(max_requests=5,  window_seconds=60)),
    ("/api/local-auth/signup",    _Limit(max_requests=5,  window_seconds=60)),
    # POS PIN login — 6-digit numeric PINs are weak; tight burst cap + lockout
    ("/api/pos/auth/pin",         _Limit(max_requests=5,  window_seconds=60)),
    # MFA — 10 attempts per minute
    ("/api/local-auth/mfa",       _Limit(max_requests=10, window_seconds=60)),
    # Refresh — cheap on the server but an open refresh endpoint is a gift
    # for a stolen-token replay tester. 30/min is well above what any legit
    # SPA needs (tokens live 15 min) and still slows a scripted abuser.
    ("/api/local-auth/refresh",   _Limit(max_requests=30, window_seconds=60)),
    # Email verification — legit users click once; a tight cap discourages
    # brute-force enumeration of verification tokens.
    ("/api/local-auth/verify-email", _Limit(max_requests=20, window_seconds=60)),
    # Password reset — 3 per hour to limit account enumeration + abuse
    ("/api/auth/password",        _Limit(max_requests=3,  window_seconds=3600)),
    ("/api/local-auth/password",  _Limit(max_requests=3,  window_seconds=3600)),
    # Portal magic-link request — 3 per hour per IP to prevent email bombing
    # and customer enumeration. Verify endpoint is per-IP 20/min (legit users
    # only click once; higher limit than login because the token is single-use).
    ("/api/portal/auth/magic-link", _Limit(max_requests=3,  window_seconds=3600)),
    ("/api/portal/auth/verify",     _Limit(max_requests=20, window_seconds=60)),
    # GDPR export — expensive, owner-only; 5 per hour is plenty
    ("/api/gdpr/export",          _Limit(max_requests=5,  window_seconds=3600)),
    # GDPR delete — extra friction on top of typed confirmation
    ("/api/gdpr/organization",    _Limit(max_requests=3,  window_seconds=3600)),
    # AI chat — GPT-4o calls cost real money. 30/hr per IP is a generous
    # cap for an interactive co-pilot while bounding the damage from a
    # compromised PRO session or a scripted abuse pattern.
    ("/api/integrations/ai/chat", _Limit(max_requests=30, window_seconds=3600)),
    # Billing — Stripe checkout/portal session creation is cheap but
    # abuse pattern is unique: an attacker with a valid session can
    # burn through Stripe's Checkout-session quotas at our expense.
    # 20/hr per IP is a generous cap for real user flows (click, back,
    # retry) and bounds the damage. Webhook is external and excluded.
    ("/api/billing/checkout",     _Limit(max_requests=20, window_seconds=3600)),
    ("/api/billing/portal",       _Limit(max_requests=20, window_seconds=3600)),
    # Eligibility — currently unshipped; reserving the bucket so the
    # endpoint inherits the throttle on landing instead of running
    # unprotected for a release cycle.
    ("/api/eligibility",          _Limit(max_requests=60, window_seconds=3600)),
    # CSV product import — bulk uploads are expensive to validate; 10/hr
    # per IP prevents a loop from exhausting a worker.
    ("/api/inventory/products/import", _Limit(max_requests=10, window_seconds=3600)),
    # Public waitlist signup — unauth'd endpoint, tempting bot target.
    # 5 per minute per IP still accommodates a small event-booth sign-up
    # queue while throttling automated spam.
    ("/api/waitlist",             _Limit(max_requests=5,  window_seconds=60)),
    # Referral generation — daily cap is enforced by business logic, but an
    # IP-level limit stops scripted link farming. 10 per hour is well above
    # any legitimate usage (real users generate once and share).
    ("/api/referrals/generate",   _Limit(max_requests=10, window_seconds=3600)),
]

# Paths that must NEVER be rate-limited. These are external callers that
# we cannot retry-backoff (Stripe webhook retries follow its own policy)
# and where a spurious 429 costs us money or integration reliability.
_BYPASS_PATHS: tuple[str, ...] = (
    "/api/billing/webhook",         # Stripe-signed; bounded by Stripe retries.
    "/api/integrations/fortnox/webhook",  # Fortnox-signed.
    "/api/health",                  # k8s liveness / Railway probes.
    "/api/healthz",
)

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
    """Return the (namespace, Limit) that applies to this path.

    Matches only on an exact path or a true sub-path (prefix followed by
    a "/"). A bare substring prefix match would cause sibling routes to
    inherit unrelated throttles — e.g. `/api/gdpr/organizations` (the
    plural listing) would pick up the 3/hr delete cap meant for
    `/api/gdpr/organization`, and `/api/waitlist-admin` would inherit
    the public-bot 5/min cap meant for `/api/waitlist`. Requiring the
    trailing "/" (or exact equality) keeps each rule scoped to its own
    endpoint subtree.
    """
    for prefix, limit in _PATH_LIMITS:
        if path == prefix or path.startswith(prefix + "/"):
            return prefix, limit
    return "__global__", _Limit(max_requests=_MAX_REQUESTS, window_seconds=_WINDOW_SECONDS)


def _is_disabled() -> bool:
    """Honour the RATE_LIMIT_DISABLED escape hatch.

    Read at call time (not module import) so tests that flip the env
    mid-run via monkeypatch see the updated value without a fresh
    process.
    """
    return bool(getattr(settings, "RATE_LIMIT_DISABLED", False))


async def _consume_memory(
    key: tuple,
    limit: _Limit,
) -> Tuple[int, Optional[float]]:
    """In-memory sliding-window counter (single-replica fallback)."""
    now = time.monotonic()
    window_start = now - limit.window_seconds
    async with _lock:
        kept = [t for t in _counters[key] if t > window_start]
        count = len(kept)
        if count >= limit.max_requests:
            oldest = kept[0]
            retry_after = float(int(limit.window_seconds - (now - oldest)) + 1)
            _counters[key] = kept
            return 0, retry_after
        kept.append(now)
        _counters[key] = kept
        if len(_counters) > 50_000:
            max_window = max(
                (lim.window_seconds for _, lim in _PATH_LIMITS),
                default=_WINDOW_SECONDS,
            )
            max_window = max(max_window, _WINDOW_SECONDS)
            eviction_cutoff = now - max_window
            stale = [k for k, ts in _counters.items() if not ts or ts[-1] <= eviction_cutoff]
            for k in stale:
                _counters.pop(k, None)
        return limit.max_requests - count - 1, None


async def _consume_redis(
    r,
    key: tuple,
    limit: _Limit,
) -> Tuple[int, Optional[float]]:
    """Redis sliding-window counter (multi-replica safe, C-1)."""
    redis_key = "rl:" + ":".join(str(k) for k in key)
    now_ms = int(time.time() * 1000)
    try:
        result = await r.eval(
            _LUA_SLIDING_WINDOW,
            1,
            redis_key,
            str(limit.window_seconds),
            str(now_ms),
            str(limit.max_requests),
        )
        remaining, retry_ms = int(result[0]), int(result[1])
        if retry_ms >= 0:
            retry_after = retry_ms / 1000.0 + 1.0
            return 0, retry_after
        return remaining, None
    except Exception:
        log.warning("Redis consume error — falling back to in-memory for this request", exc_info=True)
        return await _consume_memory(key, limit)


async def _consume(
    key: tuple,
    limit: _Limit,
) -> Tuple[int, Optional[float]]:
    """Record a hit against ``key`` and return ``(remaining, retry_after)``.

    ``retry_after`` is ``None`` when the request is admitted and a float
    (seconds) when the cap is exceeded.
    """
    r = await _get_redis()
    if r is not None:
        return await _consume_redis(r, key, limit)
    return await _consume_memory(key, limit)


def _reset_for_tests() -> None:
    """Wipe the in-memory counter and force Redis re-initialisation.

    Called from the rate-limit tests so each case starts from a clean
    state; production code must never call this.
    """
    global _redis_client, _redis_init_attempted
    _counters.clear()
    _redis_client = None
    _redis_init_attempted = False


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # Hard bypass for Stripe/Fortnox webhooks and health probes.
        if path in _BYPASS_PATHS or any(
            path.startswith(p + "/") for p in _BYPASS_PATHS
        ):
            return await call_next(request)

        if _is_disabled():
            return await call_next(request)

        ip = _client_ip(request)
        namespace, limit = _resolve_limit(path)
        key = (namespace, ip)

        remaining, retry_after = await _consume(key, limit)
        if retry_after is not None:
            log.warning(
                "Rate limit exceeded | ip=%s | path=%s | namespace=%s",
                ip, path, namespace,
            )
            reset_ts = int(time.time()) + int(retry_after)
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down."},
                headers={
                    "Retry-After":           str(int(retry_after)),
                    "X-RateLimit-Limit":     str(limit.max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset":     str(reset_ts),
                    "X-RateLimit-Window":    str(limit.window_seconds),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"]     = str(limit.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        # Expose the window so clients can implement exponential backoff
        # without re-deriving the value from the reset header.
        response.headers["X-RateLimit-Window"]    = str(limit.window_seconds)
        return response


# ── Dep-style limiters ────────────────────────────────────────────────────────
#
# These produce FastAPI dependencies. Use them as ``Depends(...)`` on a
# route to layer a stricter per-key cap on top of the middleware's
# per-(path, IP) cap. The dep raises ``HTTPException(429)`` with the
# full RateLimit-* header set so clients see the same signal shape as
# a middleware-level block.

def _raise_429(limit: _Limit, retry_after: float) -> None:
    reset_ts = int(time.time()) + int(retry_after)
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many requests. Please slow down.",
        headers={
            "Retry-After":           str(int(retry_after)),
            "X-RateLimit-Limit":     str(limit.max_requests),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset":     str(reset_ts),
            "X-RateLimit-Window":    str(limit.window_seconds),
        },
    )


def per_ip_rate_limit(bucket: str, max_requests: int, window_seconds: int) -> Callable:
    """Build a FastAPI dep that rate-limits by (bucket, client-IP).

    Use this for a "sustained" lockout on top of the middleware's
    burst cap — e.g. login is 5/min at the middleware and 20/15min
    here, so a slow drip attack that stays under the burst threshold
    still trips the sustained one.
    """
    limit = _Limit(max_requests=max_requests, window_seconds=window_seconds)

    async def _dep(request: Request) -> None:
        if _is_disabled():
            return
        ip = _client_ip(request)
        _, retry_after = await _consume((f"__ip__:{bucket}", ip), limit)
        if retry_after is not None:
            _raise_429(limit, retry_after)

    return _dep


def per_org_rate_limit(bucket: str, max_requests: int, window_seconds: int) -> Callable:
    """Build a FastAPI dep that rate-limits by (bucket, org_id).

    Pair with routes that already depend on ``get_current_member``.
    The helper resolves ``get_current_member`` independently so the
    caller does not have to re-plumb the member into every route.

    Keying on org_id (not IP) is the point: two users on the same
    corporate NAT egress should not share a quota; one compromised
    org should not starve another org's throughput.
    """
    limit = _Limit(max_requests=max_requests, window_seconds=window_seconds)

    # Imported lazily to avoid a circular at module load.
    from app.middleware.auth import get_current_member  # noqa: PLC0415

    async def _dep(current=Depends(get_current_member)) -> None:
        if _is_disabled():
            return
        _user, member = current
        key = (f"__org__:{bucket}", str(member.org_id))
        _, retry_after = await _consume(key, limit)
        if retry_after is not None:
            _raise_429(limit, retry_after)

    return _dep
