"""BankID integration — Swedish mobile e-identification.

Wraps the BankID Relying Party REST API (v6.0). The BankID auth flow
is a three-hop dance:

    init_auth()     → POST /auth        → orderRef + autoStartToken
                                          + qrStartToken + qrStartSecret
    collect()       → POST /collect     → poll until status == "complete"
                                          (carries completionData.user)
    cancel()        → POST /cancel      → abort an outstanding order

Docs: https://developers.bankid.com/api-references/auth--sign/auth

The module is deliberately thin: no retries (BankID wants the client to
poll every 2 seconds — we honour that by letting the caller drive the
cadence), no caching (orderRef is one-shot), and no persistence (the
router decides what to do with the result).

In the BankID test environment (the default) no real personnummer is
returned; any test-BankID user is synthetic. Production requires a
relying-party certificate issued by Finansiell ID-Teknik BID AB — set
``BANKID_CLIENT_CERT_PATH`` to the PEM file before switching URLs.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger(__name__)


class BankIDError(Exception):
    """Wraps any error talking to the BankID backend."""


class BankIDNotConfigured(BankIDError):
    """Raised when the relying-party certificate is missing."""


def _client() -> httpx.AsyncClient:
    """Build a mTLS httpx client against the configured BankID host.

    Production requires both a client certificate and the BankID CA
    bundle. In the test environment the cert is optional — operators
    can hit the endpoints from curl to smoke-test, but the real auth
    calls will be rejected by BankID without proper mutual TLS.
    """
    if not settings.BANKID_CLIENT_CERT_PATH:
        raise BankIDNotConfigured(
            "BANKID_CLIENT_CERT_PATH is empty — provision a relying-party cert",
        )
    verify: bool | str = settings.BANKID_CA_CERT_PATH or True
    return httpx.AsyncClient(
        base_url=settings.BANKID_API_URL,
        cert=settings.BANKID_CLIENT_CERT_PATH,
        verify=verify,
        timeout=httpx.Timeout(10.0),
        headers={"Content-Type": "application/json"},
    )


def _mask_pnr(raw: str | None) -> str:
    """Return a loggable fragment of a personnummer (last 4 redacted)."""
    if not raw:
        return "<none>"
    raw = raw.strip()
    if len(raw) < 4:
        return "<short>"
    return raw[:-4] + "****"


def normalise_personnummer(raw: str) -> str:
    """Return the canonical 12-digit personnummer.

    BankID returns the 12-digit form (``YYYYMMDDNNNN``) so this is
    mostly a defensive check. We strip hyphens and plus signs just in
    case a future BankID SDK hands us the 10-digit legacy form.
    """
    digits = "".join(c for c in raw if c.isdigit())
    if len(digits) == 12:
        return digits
    raise BankIDError(f"personalNumber has unexpected length {len(digits)}")


def hash_personnummer(raw: str) -> str:
    """SHA-256 hex digest of the canonical 12-digit personnummer."""
    return hashlib.sha256(normalise_personnummer(raw).encode("utf-8")).hexdigest()


async def init_auth(*, end_user_ip: str) -> dict[str, Any]:
    """Start a BankID auth order.

    ``end_user_ip`` is required by BankID so fraud signals can be
    correlated back to the client — they reject requests where the IP
    looks forged (e.g. 127.0.0.1 from a public LB).
    """
    payload = {
        "endUserIp": end_user_ip,
        # We don't request any personalNumber — "auth" without a
        # pre-filled personnummer is the standard consumer flow: the
        # user picks which BankID to use on their own device.
    }
    async with _client() as c:
        try:
            r = await c.post("/auth", json=payload)
        except httpx.HTTPError as e:
            raise BankIDError(f"bankid /auth transport error: {e}") from e
    if r.status_code != 200:
        raise BankIDError(
            f"bankid /auth failed status={r.status_code} body={r.text[:500]}"
        )
    return r.json()


async def collect(*, order_ref: str) -> dict[str, Any]:
    """Poll BankID for the current status of an outstanding auth order.

    Returns the parsed body verbatim — the caller branches on
    ``status`` (``pending`` / ``complete`` / ``failed``).
    """
    async with _client() as c:
        try:
            r = await c.post("/collect", json={"orderRef": order_ref})
        except httpx.HTTPError as e:
            raise BankIDError(f"bankid /collect transport error: {e}") from e
    if r.status_code != 200:
        raise BankIDError(
            f"bankid /collect failed status={r.status_code} body={r.text[:500]}"
        )
    return r.json()


async def cancel(*, order_ref: str) -> None:
    """Best-effort cancel. Failures are logged and swallowed."""
    try:
        async with _client() as c:
            await c.post("/cancel", json={"orderRef": order_ref})
    except (BankIDError, httpx.HTTPError) as e:
        log.info("bankid cancel failed (swallowed) order=%s err=%s", order_ref, e)


def build_qr_data(*, qr_start_token: str, qr_start_secret: str, start_time: float) -> str:
    """Compute the animated-QR payload for a given second.

    BankID shows a new QR every second while the user is expected to
    still be scanning. The payload format is::

        bankid.<qrStartToken>.<qrTime>.<qrAuthCode>

    where ``qrTime`` is the integer number of seconds since the
    ``init_auth`` response was received, and ``qrAuthCode`` is the
    hex-encoded HMAC-SHA256 of that integer (as ASCII digits) keyed by
    ``qrStartSecret``.

    The caller should invoke this once per poll (~1 s) with a stable
    ``start_time`` captured when the order was created; passing
    ``time.time()`` will drift one second per call.
    """
    qr_time = str(int(time.time() - start_time))
    qr_auth_code = hmac.new(
        key=qr_start_secret.encode("ascii"),
        msg=qr_time.encode("ascii"),
        digestmod=hashlib.sha256,
    ).hexdigest()
    return f"bankid.{qr_start_token}.{qr_time}.{qr_auth_code}"
