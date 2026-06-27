"""E-invoice (Peppol BIS 3.0 / E-faktura) export router.

Provides plan-gated, audited Peppol BIS Billing 3.0 UBL 2.1 XML generation
and external validation against the Swedish SFTI validator.

The raw XML generator lives in ``app.routers.invoicing._generate_peppol_xml``;
this router layers plan enforcement, Swedish VAT format validation, and
audit-trail logging on top of it.
"""
from __future__ import annotations

import logging
import re
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_plan
from app.features.invoicing.models import Invoice
from app.features.auth.organization import Organization, OrgPlan
from app.features.invoicing.router import _generate_peppol_xml
from app.services.audit import log_action

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/einvoice", tags=["einvoice"])

# Swedish VAT number format: "SE" + 12 digits = 14 characters total.
# See Skatteverket MomsRegNr spec and EU VIES. The trailing 2 digits are
# usually "01" but we don't enforce that — just shape.
_SE_VAT_RE = re.compile(r"^SE\d{12}$")

# Per SFTI: https://validate.sfti.se — public endpoint for Peppol BIS
# Billing 3.0 schematron validation.
SFTI_VALIDATE_URL = "https://validate.sfti.se/validate"
_SFTI_TIMEOUT = httpx.Timeout(connect=5.0, read=20.0, write=10.0, pool=5.0)


def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


async def _load_invoice_and_org(
    invoice_id: uuid.UUID, org_id: uuid.UUID, db: AsyncSession
) -> tuple[Invoice, Organization]:
    result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.customer), selectinload(Invoice.line_items))
        .where(Invoice.id == invoice_id, Invoice.org_id == org_id)
    )
    inv = result.scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    org = await db.get(Organization, org_id)
    if org is None:  # pragma: no cover — FK guarantees existence
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    return inv, org


def _assert_swedish_vat(org: Organization) -> None:
    """Enforce Swedish VAT format on the supplier (= organisation).

    Peppol BIS Billing 3.0 requires a syntactically valid VAT identifier
    on the AccountingSupplierParty. For SE-issued invoices Skatteverket
    mandates ``SE`` + 12 digits. Raise 422 with a precise error rather
    than emit a non-compliant XML that SFTI will reject anyway.
    """
    vat = (org.vat_number or "").strip().upper().replace(" ", "")
    if not _SE_VAT_RE.match(vat):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Supplier VAT number must be a Swedish VAT id in the form "
                "'SE' followed by 12 digits (14 characters total). "
                "Set it in Settings → Organisation."
            ),
        )


@router.post("/peppol/{invoice_id}")
async def export_peppol_xml(
    invoice_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_plan(OrgPlan.PRO)),
) -> Response:
    """Generate a Peppol BIS Billing 3.0 UBL 2.1 XML for an invoice.

    Returns the XML as ``application/xml`` with a content-disposition
    attachment so the browser downloads the file. Logs ``PEPPOL_EXPORT``
    in the audit trail regardless of browser behaviour.
    """
    user, member = ctx
    org_id = member.org_id

    inv, org = await _load_invoice_and_org(invoice_id, org_id, db)
    _assert_swedish_vat(org)

    xml_bytes = _generate_peppol_xml(inv, org)
    filename = f"varuflow-invoice-{inv.invoice_number}.xml"

    await log_action(
        db,
        action="PEPPOL_EXPORT",
        org_id=org_id,
        actor_user_id=user["user_id"],
        target_type="invoice",
        target_id=str(inv.id),
        request=request,
        extra={"invoice_number": inv.invoice_number, "size_bytes": len(xml_bytes)},
    )
    await db.commit()

    return Response(
        content=xml_bytes,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/peppol/{invoice_id}/validate")
async def validate_peppol_xml(
    invoice_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_plan(OrgPlan.PRO)),
) -> dict:
    """Submit the invoice XML to SFTI's public validator.

    Returns ``{"passed": bool, "errors": [...], "warnings": [...]}``. The
    downstream service is best-effort: if SFTI is unreachable we surface
    a 503 rather than fabricating a pass/fail verdict.
    """
    user, member = ctx
    org_id = member.org_id

    inv, org = await _load_invoice_and_org(invoice_id, org_id, db)
    _assert_swedish_vat(org)

    xml_bytes = _generate_peppol_xml(inv, org)

    try:
        async with httpx.AsyncClient(timeout=_SFTI_TIMEOUT) as client:
            resp = await client.post(
                SFTI_VALIDATE_URL,
                content=xml_bytes,
                headers={"Content-Type": "application/xml", "Accept": "application/json"},
            )
    except httpx.HTTPError as e:
        log.warning("sfti_validate_unreachable | err=%s", str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SFTI validator is currently unreachable. Please try again.",
        ) from None

    # SFTI returns JSON on success, plain text on upstream failure. Tolerate
    # both — never trust downstream to be well-formed.
    try:
        payload = resp.json()
    except ValueError:
        payload = {"raw": resp.text[:2000]}

    errors = payload.get("errors") if isinstance(payload, dict) else None
    warnings = payload.get("warnings") if isinstance(payload, dict) else None
    passed = resp.status_code == 200 and not errors

    await log_action(
        db,
        action="PEPPOL_VALIDATE",
        org_id=org_id,
        actor_user_id=user["user_id"],
        target_type="invoice",
        target_id=str(inv.id),
        request=request,
        extra={
            "invoice_number": inv.invoice_number,
            "passed": passed,
            "sfti_status": resp.status_code,
            "error_count": len(errors) if isinstance(errors, list) else 0,
        },
    )
    await db.commit()

    return {
        "passed": passed,
        "status_code": resp.status_code,
        "errors": errors or [],
        "warnings": warnings or [],
    }
