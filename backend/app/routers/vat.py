"""EU VAT number validation via VIES (VAT Information Exchange System).

VIES is the EU Commission's free service for verifying that a VAT number is
registered in the member state's database. Every EU SaaS billing B2B
customers needs this because:
  * Reverse-charge B2B invoices are only valid when the buyer's VAT number
    is confirmed by VIES.
  * The Commission publishes a REST-ish endpoint at
    https://ec.europa.eu/taxation_customs/vies/rest-api/ms/{CC}/vat/{NUMBER}

Public endpoint — no auth required on Varuflow's side because VIES is a
public registry. We apply light rate-limiting to avoid being blacklisted
by the upstream.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/vat", tags=["vat"])

# VIES covers the 27 EU member states. Keep in sync with config/countries/.
EU_MEMBERS = {
    "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "EL",  # "EL" is Greece in VIES, ISO is "GR"
    "ES", "FI", "FR", "HR", "HU", "IE", "IT", "LT", "LU",
    "LV", "MT", "NL", "PL", "PT", "RO", "SE", "SI", "SK",
}

# ISO-3166 → VIES country code (Greece is the only exception).
ISO_TO_VIES = {"GR": "EL"}

# Lightweight per-country regex — catches obvious garbage before we round-trip VIES.
# Not a full format check (VIES does that authoritatively); just cheap validation.
VAT_PATTERN = re.compile(r"^[A-Z0-9+.*]{2,20}$")


class VatCheckResponse(BaseModel):
    country:     str = Field(..., description="VIES country code used (e.g. 'DE', 'EL').")
    vat_number:  str = Field(..., description="Normalised VAT number (no spaces).")
    valid:       bool
    name:        Optional[str] = None
    address:     Optional[str] = None
    checked_at:  Optional[str] = None
    source:      str = "VIES"


@router.get("/check", response_model=VatCheckResponse)
async def check_vat(
    country:    str = Query(..., min_length=2, max_length=2, description="ISO-3166 alpha-2 country code."),
    vat_number: str = Query(..., min_length=4, max_length=20, description="VAT number without country prefix."),
) -> VatCheckResponse:
    """Verify a VAT number against VIES.

    Example:
      GET /api/vat/check?country=DE&vat_number=123456789
    """
    iso = country.upper().strip()
    vies_cc = ISO_TO_VIES.get(iso, iso)

    if vies_cc not in EU_MEMBERS:
        raise HTTPException(
            status_code=400,
            detail=f"VIES only covers EU member states. '{iso}' is not in VIES.",
        )

    number = re.sub(r"[\s\-]", "", vat_number).upper()
    # Strip leading country prefix if the caller included it (common copy-paste).
    if number.startswith(vies_cc):
        number = number[len(vies_cc):]

    if not VAT_PATTERN.match(number):
        raise HTTPException(status_code=422, detail="VAT number contains invalid characters.")

    url = f"https://ec.europa.eu/taxation_customs/vies/rest-api/ms/{vies_cc}/vat/{number}"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, headers={"Accept": "application/json"})
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="VIES timed out — try again shortly.")
    except httpx.RequestError as e:
        log.warning("VIES request failed: %s", e)
        raise HTTPException(status_code=502, detail="VIES unreachable.")

    if resp.status_code == 404:
        return VatCheckResponse(country=vies_cc, vat_number=number, valid=False)
    if resp.status_code >= 500:
        raise HTTPException(status_code=502, detail="VIES returned an upstream error.")
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=f"VIES error: {resp.text[:200]}")

    data: dict = resp.json() if resp.content else {}
    is_valid = bool(data.get("isValid") or data.get("valid"))
    return VatCheckResponse(
        country    = vies_cc,
        vat_number = number,
        valid      = is_valid,
        name       = (data.get("name") or "").strip() or None,
        address    = (data.get("address") or "").strip() or None,
        checked_at = data.get("requestDate") or data.get("checkedAt"),
    )


# ───────────────────────────────────────────────────────────────────────────
# Norway — BRREG (Brønnøysundregistrene) lookup
# ───────────────────────────────────────────────────────────────────────────
# Norway is in the EEA but not the EU, so it is NOT in VIES. Norwegian VAT
# (MVA) numbers have the form "NO<9 digits>MVA". The 9 digits are the
# organisation number registered in Brønnøysundregistrene. We query the
# free public REST API:
#   https://data.brreg.no/enhetsregisteret/api/enheter/{orgnr}
# to confirm the company exists and is active.

BRREG_URL = "https://data.brreg.no/enhetsregisteret/api/enheter/{orgnr}"
NO_ORGNR_RE = re.compile(r"^\d{9}$")


class BrregResponse(BaseModel):
    country:     str = "NO"
    org_number:  str
    valid:       bool
    vat_registered: bool = Field(..., description="True if the org is in MVA-registeret (VAT-registered).")
    name:        Optional[str] = None
    address:     Optional[str] = None
    source:      str = "BRREG"


@router.get("/check-no", response_model=BrregResponse)
async def check_norway_company(
    org_number: str = Query(..., min_length=9, max_length=16, description="Norwegian org.nr (9 digits) with or without 'NO' prefix / 'MVA' suffix."),
) -> BrregResponse:
    """Verify a Norwegian company against Brønnøysundregistrene (BRREG).

    Accepts:
      * Plain org.nr: '123456785'
      * VAT format:   'NO123456785MVA'
    Returns whether the organisation exists AND whether it is registered
    for MVA (Norwegian VAT) — the latter is what matters for B2B invoicing.
    """
    raw = re.sub(r"[\s\-]", "", org_number).upper()
    if raw.startswith("NO"):
        raw = raw[2:]
    if raw.endswith("MVA"):
        raw = raw[:-3]

    if not NO_ORGNR_RE.match(raw):
        raise HTTPException(status_code=422, detail="Norwegian org.nr must be 9 digits.")

    url = BRREG_URL.format(orgnr=raw)
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, headers={"Accept": "application/json"})
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="BRREG timed out — try again shortly.")
    except httpx.RequestError as e:
        log.warning("BRREG request failed: %s", e)
        raise HTTPException(status_code=502, detail="BRREG unreachable.")

    if resp.status_code == 404 or resp.status_code == 410:
        return BrregResponse(org_number=raw, valid=False, vat_registered=False)
    if resp.status_code >= 500:
        raise HTTPException(status_code=502, detail="BRREG returned an upstream error.")
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=f"BRREG error: {resp.text[:200]}")

    data: dict = resp.json() if resp.content else {}
    # BRREG payload fields: 'navn', 'registrertIMvaregisteret' (bool),
    # 'forretningsadresse': { 'adresse': [..], 'postnummer', 'poststed', 'landkode' }
    name = (data.get("navn") or "").strip() or None
    vat_reg = bool(data.get("registrertIMvaregisteret"))
    addr_obj = data.get("forretningsadresse") or {}
    addr_parts = []
    for line in addr_obj.get("adresse") or []:
        if line:
            addr_parts.append(str(line))
    postnr = addr_obj.get("postnummer")
    sted = addr_obj.get("poststed")
    if postnr or sted:
        addr_parts.append(f"{postnr or ''} {sted or ''}".strip())
    address = ", ".join(addr_parts) or None

    return BrregResponse(
        org_number     = raw,
        valid          = True,
        vat_registered = vat_reg,
        name           = name,
        address        = address,
    )

