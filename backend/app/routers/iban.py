"""IBAN validation — local mod-97 check, no external service required.

IBAN (ISO 13616) is validated by:
  1. Length matches the country-specific expected length.
  2. Move the first 4 characters to the end (country code + check digits).
  3. Replace each letter with two digits (A=10, B=11, …, Z=35).
  4. The resulting integer mod 97 must equal 1.

This catches 99.9% of typos. Does not prove the account exists — only that
the number is well-formed and its check digits are correct. SEPA payments
require a valid IBAN; this is a mandatory client-side + server-side guard.
"""
from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/iban", tags=["iban"])

# ISO 13616 registered IBAN lengths. Covers all SEPA + most of the world.
IBAN_LENGTHS: dict[str, int] = {
    "AD": 24, "AE": 23, "AL": 28, "AT": 20, "AZ": 28, "BA": 20, "BE": 16,
    "BG": 22, "BH": 22, "BR": 29, "BY": 28, "CH": 21, "CR": 22, "CY": 28,
    "CZ": 24, "DE": 22, "DK": 18, "DO": 28, "EE": 20, "ES": 24, "FI": 18,
    "FO": 18, "FR": 27, "GB": 22, "GE": 22, "GI": 23, "GL": 18, "GR": 27,
    "GT": 28, "HR": 21, "HU": 28, "IE": 22, "IL": 23, "IS": 26, "IT": 27,
    "JO": 30, "KW": 30, "KZ": 20, "LB": 28, "LC": 32, "LI": 21, "LT": 20,
    "LU": 20, "LV": 21, "MC": 27, "MD": 24, "ME": 22, "MK": 19, "MR": 27,
    "MT": 31, "MU": 30, "NL": 18, "NO": 15, "PK": 24, "PL": 28, "PS": 29,
    "PT": 25, "QA": 29, "RO": 24, "RS": 22, "SA": 24, "SE": 24, "SI": 19,
    "SK": 24, "SM": 27, "ST": 25, "SV": 28, "TL": 23, "TN": 24, "TR": 26,
    "UA": 29, "VA": 22, "VG": 24, "XK": 20,
}

IBAN_CHARS = re.compile(r"^[A-Z0-9]+$")


class IbanResponse(BaseModel):
    iban:     str
    valid:    bool
    country:  Optional[str] = None
    reason:   Optional[str] = None


def _validate(raw: str) -> tuple[bool, str, Optional[str]]:
    normalised = re.sub(r"\s", "", raw or "").upper()
    if len(normalised) < 15 or len(normalised) > 34:
        return False, normalised, "Length out of IBAN range."
    if not IBAN_CHARS.match(normalised):
        return False, normalised, "Contains non-alphanumeric characters."
    country = normalised[:2]
    expected = IBAN_LENGTHS.get(country)
    if expected is None:
        return False, normalised, f"Unknown country code '{country}'."
    if len(normalised) != expected:
        return False, normalised, f"Expected {expected} chars for {country}, got {len(normalised)}."
    # Mod-97: move first 4 chars to end, replace letters with 10..35, then int % 97 == 1.
    rearranged = normalised[4:] + normalised[:4]
    converted = "".join(str(ord(c) - 55) if c.isalpha() else c for c in rearranged)
    try:
        ok = int(converted) % 97 == 1
    except ValueError:
        return False, normalised, "Conversion failed."
    return (True, normalised, None) if ok else (False, normalised, "Check-digit failure.")


@router.get("/check", response_model=IbanResponse)
async def check_iban(iban: str = Query(..., min_length=5, max_length=64)) -> IbanResponse:
    """Validate IBAN length + country + mod-97 checksum. No network call."""
    try:
        ok, normalised, reason = _validate(iban)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"IBAN malformed: {e}") from e
    return IbanResponse(
        iban    = normalised,
        valid   = ok,
        country = normalised[:2] if len(normalised) >= 2 else None,
        reason  = reason,
    )
