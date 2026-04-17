"""Tax logic — EU B2B reverse-charge rules + Norwegian MVA handling.

The core question every EU wholesaler asks per invoice:
  "Do I charge my local VAT, charge the buyer's VAT, or zero-rate with a
   reverse-charge note?"

Simplified rules implemented here (services & goods, common case):

  1. Seller and buyer in SAME country → seller's domestic VAT applies.
  2. Seller in EU, buyer in EU, DIFFERENT country, buyer has valid VAT ID
     → reverse-charge, 0% VAT. Invoice must show both VAT numbers and the
       text "Reverse charge — Article 196 of Council Directive 2006/112/EC".
  3. Seller in EU, buyer in EU, DIFFERENT country, buyer has NO valid VAT ID
     → distance-sale: seller must charge buyer-country VAT (OSS scheme).
       We flag but don't compute OSS — that's Phase 2.
  4. Seller in EU, buyer outside EU → exempt, 0%. Export.
  5. Seller in Norway, buyer in Norway → Norwegian MVA (25% / 15% / 12%).
  6. Seller in Norway, buyer outside Norway → exempt, 0%. Export.
  7. Seller outside EU/EEA, buyer inside → buyer handles import VAT; seller
     issues 0%.

This is NOT tax advice. Regulations change. Users must confirm with their
accountant — but this router gives sensible defaults that handle ~95% of
Varuflow's real wholesaler flows.
"""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/tax", tags=["tax"])

EU_MEMBERS = {
    "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR",
    "GR", "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT", "NL", "PL",
    "PT", "RO", "SE", "SI", "SK",
}
EEA_NON_EU = {"NO", "IS", "LI"}


class ReverseChargeRequest(BaseModel):
    seller_country: str = Field(..., min_length=2, max_length=2)
    buyer_country:  str = Field(..., min_length=2, max_length=2)
    buyer_vat_valid: bool = Field(
        default=False,
        description="True if buyer's VAT number has been verified with VIES (or BRREG for NO).",
    )
    buyer_is_business: bool = Field(default=True)


TreatmentKind = Literal[
    "domestic",           # seller's standard VAT rate
    "reverse_charge",     # 0% VAT, note on invoice, EU B2B cross-border
    "export",             # 0% VAT, outside EU/EEA
    "oss_distance_sale",  # charge buyer-country VAT via OSS scheme (B2C cross-border)
    "unknown",
]


class ReverseChargeResponse(BaseModel):
    treatment:   TreatmentKind
    vat_rate:    Optional[float] = Field(None, description="Null means 'use the invoice's own per-line rates (domestic)'.")
    zero_rate:   bool
    legal_note:  Optional[str] = Field(None, description="Text that must appear on the invoice PDF.")
    explanation: str


def _decide(seller: str, buyer: str, vat_valid: bool, is_business: bool) -> ReverseChargeResponse:
    s, b = seller.upper(), buyer.upper()

    # Rule 1 — same country
    if s == b:
        return ReverseChargeResponse(
            treatment=  "domestic",
            vat_rate=   None,
            zero_rate=  False,
            legal_note= None,
            explanation="Same-country sale — apply seller's domestic VAT rates.",
        )

    seller_in_eu = s in EU_MEMBERS
    buyer_in_eu  = b in EU_MEMBERS
    seller_in_no = s == "NO"
    buyer_in_no  = b == "NO"

    # Rule 2 + 3 — EU ↔ EU cross-border
    if seller_in_eu and buyer_in_eu:
        if is_business and vat_valid:
            return ReverseChargeResponse(
                treatment=  "reverse_charge",
                vat_rate=   0.0,
                zero_rate=  True,
                legal_note= "Reverse charge — Article 196 of Council Directive 2006/112/EC. VAT to be accounted for by the recipient.",
                explanation="EU B2B cross-border with verified VAT ID → 0% VAT, buyer self-accounts.",
            )
        return ReverseChargeResponse(
            treatment=  "oss_distance_sale",
            vat_rate=   None,
            zero_rate=  False,
            legal_note= "Distance sale within the EU — apply destination-country VAT via OSS.",
            explanation="EU cross-border without a valid buyer VAT ID → OSS scheme (buyer-country VAT).",
        )

    # Rule 4 — EU seller, non-EU buyer
    if seller_in_eu and not buyer_in_eu:
        return ReverseChargeResponse(
            treatment=  "export",
            vat_rate=   0.0,
            zero_rate=  True,
            legal_note= "Export outside the EU — exempt from VAT under Article 146 of Directive 2006/112/EC.",
            explanation="Goods/services leaving the EU → zero-rated export.",
        )

    # Rule 5 + 6 — Norway seller
    if seller_in_no:
        if buyer_in_no:
            return ReverseChargeResponse(
                treatment=  "domestic",
                vat_rate=   None,
                zero_rate=  False,
                legal_note= None,
                explanation="Norwegian domestic sale — apply MVA at standard/reduced rates.",
            )
        return ReverseChargeResponse(
            treatment=  "export",
            vat_rate=   0.0,
            zero_rate=  True,
            legal_note= "Eksport — fritatt fra merverdiavgift (Mval. § 6-21).",
            explanation="Export from Norway → exempt from MVA.",
        )

    # Rule 7 — non-EU/non-NO seller selling into EU
    if not seller_in_eu and not seller_in_no and (buyer_in_eu or buyer_in_no):
        return ReverseChargeResponse(
            treatment=  "reverse_charge" if is_business else "export",
            vat_rate=   0.0,
            zero_rate=  True,
            legal_note= "Import — VAT to be accounted for by the recipient upon importation.",
            explanation="Cross-border import into EU/EEA → seller issues 0%, buyer handles import VAT.",
        )

    return ReverseChargeResponse(
        treatment=  "unknown",
        vat_rate=   None,
        zero_rate=  False,
        legal_note= None,
        explanation="Tax treatment could not be determined automatically — review with your accountant.",
    )


@router.post("/reverse-charge", response_model=ReverseChargeResponse)
async def reverse_charge(req: ReverseChargeRequest) -> ReverseChargeResponse:
    """Decide VAT treatment for a single invoice based on seller + buyer context."""
    return _decide(req.seller_country, req.buyer_country, req.buyer_vat_valid, req.buyer_is_business)
