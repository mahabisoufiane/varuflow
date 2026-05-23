"""Country resolution service.

Resolves the "active country" for an incoming request. Used to drive
per-country VAT rates, currency defaults, invoice numbering, and locale.

Resolution order (first match wins):
  1. `X-Country-Code` header (explicit override, for API clients)
  2. Subdomain prefix of the Origin / Host header (e.g. de.varuflow.app → DE)
  3. The authenticated organization's stored country code
  4. `DEFAULT_COUNTRY` env var (defaults to `SE`)

The resolved country is attached to `request.state.country` by
`app.middleware.country.CountryMiddleware` so downstream routers can use it
without re-parsing.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import Request

_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent.parent / "config" / "countries"
_DEFAULT = os.getenv("DEFAULT_COUNTRY", "SE").upper()


@lru_cache(maxsize=1)
def _index() -> dict[str, dict[str, Any]]:
    """Cache the per-country config in memory. Reloaded only on process restart."""
    out: dict[str, dict[str, Any]] = {}
    if not _CONFIG_DIR.is_dir():
        return out
    for path in _CONFIG_DIR.glob("*.json"):
        if path.name == "index.json":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        code = data.get("iso_alpha2") or path.stem
        out[code.upper()] = data
    return out


def known_countries() -> list[str]:
    return sorted(_index().keys())


def get_country_config(code: str) -> dict[str, Any] | None:
    return _index().get(code.upper())


def _from_subdomain(host: str | None) -> str | None:
    """Extract a 2-letter country code from the first label of `host`.

    Only returns a match when the label is exactly 2 letters and is known
    in the country index — avoids treating `www` or `api` as a country.
    """
    if not host:
        return None
    label = host.split(".", 1)[0].strip().upper()
    if len(label) == 2 and label in _index():
        return label
    return None


def resolve_country(request: Request, org_country: str | None = None) -> str:
    """Return the resolved ISO-3166 alpha-2 code for this request."""
    # 1. Explicit header
    header = request.headers.get("x-country-code")
    if header:
        code = header.strip().upper()
        if code in _index():
            return code

    # 2. Subdomain
    sub = _from_subdomain(request.headers.get("host"))
    if sub:
        return sub

    # 3. Organization setting
    if org_country:
        code = org_country.strip().upper()
        if code in _index():
            return code

    # 4. Process default (validated at startup)
    return _DEFAULT if _DEFAULT in _index() else "SE"
