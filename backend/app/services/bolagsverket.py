"""Bolagsverket company lookup (Swedish Companies Registration Office).

Looks up Swedish legal entities by organisationsnummer. The external
API is optional — if ``settings.BOLAGSVERKET_API_URL`` is empty the
service returns a minimally-useful stub so local/dev environments
work without the production credential.

Results are cached in-process with a 6 h TTL because Bolagsverket
data is effectively immutable at invoice-timescale: a company name
or address almost never changes between customer-lookup calls
within a single workday, and keeping the network fan-out low avoids
exhausting the shared API rate limit on a shared production host.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger(__name__)

# Sweden orgnr: 10 digits, optionally split by a hyphen after digit 6
# (e.g. "556000-0001"). Accept either form.
_ORGNR_RE = re.compile(r"^\d{6}-?\d{4}$")


# (value, expires_at_epoch)
_cache: dict[str, tuple[dict[str, Any], float]] = {}
_CACHE_TTL_SECONDS = 6 * 60 * 60


def normalise_orgnr(orgnr: str) -> str | None:
    """Return the 10-digit form or ``None`` if the input is not a valid
    Swedish orgnr. Validates format AND Luhn checksum — a typo in any
    digit rejects, which prevents cache pollution with invalid keys."""
    if not orgnr:
        return None
    candidate = orgnr.strip().replace(" ", "")
    if not _ORGNR_RE.match(candidate):
        return None
    digits = candidate.replace("-", "")
    if len(digits) != 10:
        return None
    # Luhn (MOD-10) check on the 10 digits — Skatteverket's published
    # validation rule for Swedish organisationsnummer.
    total = 0
    for i, ch in enumerate(digits):
        n = int(ch)
        if i % 2 == 0:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    if total % 10 != 0:
        return None
    return digits


def _cache_get(key: str) -> dict[str, Any] | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    value, expires = entry
    if expires < time.time():
        _cache.pop(key, None)
        return None
    return value


def _cache_set(key: str, value: dict[str, Any]) -> None:
    _cache[key] = (value, time.time() + _CACHE_TTL_SECONDS)


def _stub_response(orgnr: str) -> dict[str, Any]:
    """Return a shape-compatible response when no API is configured.

    The frontend still renders the form pre-fill — it just shows
    ``status: not_configured`` so QA knows the live API wasn't hit.
    """
    return {
        "status": "not_configured",
        "org_number": orgnr,
        "company_name": None,
        "vat_number": None,
        "address": None,
        "postal_code": None,
        "city": None,
        "registered_date": None,
    }


async def lookup_company(orgnr: str) -> dict[str, Any]:
    """Look up a company by organisationsnummer.

    Raises nothing — on network failure the function logs and returns
    ``{"status": "error"}`` so the caller can present a soft-fail UX.
    """
    normalised = normalise_orgnr(orgnr)
    if not normalised:
        return {"status": "invalid", "org_number": orgnr}

    cached = _cache_get(normalised)
    if cached is not None:
        return cached

    if not settings.BOLAGSVERKET_API_URL:
        result = _stub_response(normalised)
        _cache_set(normalised, result)
        return result

    headers = {"Accept": "application/json"}
    if settings.BOLAGSVERKET_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.BOLAGSVERKET_API_TOKEN}"

    url = f"{settings.BOLAGSVERKET_API_URL.rstrip('/')}/companies/{normalised}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(url, headers=headers)
    except (httpx.TimeoutException, httpx.HTTPError) as e:
        log.warning("bolagsverket lookup failed orgnr=%s: %s", normalised, e)
        return {"status": "error", "org_number": normalised}

    if res.status_code == 404:
        return {"status": "not_found", "org_number": normalised}
    if res.status_code >= 400:
        log.warning(
            "bolagsverket lookup %s returned %s", normalised, res.status_code,
        )
        return {"status": "error", "org_number": normalised}

    try:
        payload = res.json()
    except ValueError:
        return {"status": "error", "org_number": normalised}

    # Bolagsverket's real API returns many fields; normalise to the
    # small shape the frontend actually consumes. Missing keys default
    # to None rather than crashing the payload.
    result = {
        "status": "ok",
        "org_number": normalised,
        "company_name": payload.get("name") or payload.get("company_name"),
        "vat_number": payload.get("vat_number") or f"SE{normalised}01",
        "address": payload.get("address") or payload.get("street_address"),
        "postal_code": payload.get("postal_code"),
        "city": payload.get("city"),
        "registered_date": payload.get("registered_date"),
    }
    _cache_set(normalised, result)
    return result
