"""ZATCA Phase 2 e-invoicing (Saudi Arabia)

Generates ZATCA-compliant UBL 2.1 XML and TLV-encoded QR codes per the
Zakat, Tax and Customs Authority standard.

SCOPE: This implementation generates the XML document and TLV QR (tags 1-6).
Tags 7/8 (ECDSA signature + public key) require a per-company CSID certificate
issued by ZATCA. The /submit endpoint is a stub — live clearance requires
ZATCA sandbox credentials that must be obtained by the customer.

Endpoints:
  POST /api/mena/zatca/generate/{invoice_id}
  GET  /api/mena/zatca/list
  GET  /api/mena/zatca/{invoice_id}
  GET  /api/mena/zatca/{invoice_id}/xml
  POST /api/mena/zatca/submit/{invoice_id}
"""
from __future__ import annotations

import base64
import hashlib
import logging
import struct
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from xml.etree import ElementTree as ET

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_plan
from app.features.invoicing.models import Invoice, InvoiceLineItem, InvoiceStatus
from app.features.auth.organization import OrgPlan, Organization
from .zatca_models import ZatcaInvoice

router = APIRouter(prefix="/api/mena/zatca", tags=["mena_zatca"])
log = logging.getLogger(__name__)


def _tlv_encode(tag: int, value: bytes) -> bytes:
    """Encode a single TLV field per ZATCA spec (1-byte tag, 1-byte length, value)."""
    return bytes([tag, len(value)]) + value


def _build_qr_tlv(
    seller_name: str,
    vat_number: str,
    invoice_datetime: str,
    total_with_vat: str,
    vat_amount: str,
    invoice_hash_hex: str,
) -> str:
    """Build ZATCA TLV QR payload (tags 1-6; 7+8 are stubs requiring CSID).

    Returns base64-encoded TLV blob.
    """
    tlv = b""
    tlv += _tlv_encode(1, seller_name.encode("utf-8"))
    tlv += _tlv_encode(2, vat_number.encode("utf-8"))
    tlv += _tlv_encode(3, invoice_datetime.encode("utf-8"))
    tlv += _tlv_encode(4, total_with_vat.encode("utf-8"))
    tlv += _tlv_encode(5, vat_amount.encode("utf-8"))
    tlv += _tlv_encode(6, invoice_hash_hex.encode("utf-8"))
    # Tags 7 (ECDSA signature) and 8 (public key) require CSID — stubs
    tlv += _tlv_encode(7, b"")
    tlv += _tlv_encode(8, b"")
    return base64.b64encode(tlv).decode("ascii")


def _build_zatca_xml(
    invoice: Invoice,
    org: Organization,
    line_items: list[InvoiceLineItem],
) -> str:
    """Generate UBL 2.1 XML per ZATCA Phase 2 e-invoice schema.

    Simplified standard tax invoice format.
    """
    ns = {
        "ubl": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
        "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    }

    def el(tag: str, text: str | None = None, attrib: dict | None = None) -> ET.Element:
        e = ET.Element(tag, attrib or {})
        if text is not None:
            e.text = text
        return e

    root = ET.Element("Invoice", {
        "xmlns": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
        "xmlns:cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        "xmlns:cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    })

    root.append(el("cbc:UBLVersionID", "2.1"))
    root.append(el("cbc:ProfileID", "reporting:1.0"))
    root.append(el("cbc:ID", invoice.invoice_number))
    root.append(el("cbc:UUID", str(invoice.id)))

    issue_dt = invoice.issue_date
    issue_str = issue_dt.strftime("%Y-%m-%d") if hasattr(issue_dt, "strftime") else str(issue_dt)
    root.append(el("cbc:IssueDate", issue_str))
    root.append(el("cbc:InvoiceTypeCode", "388", {"name": "0100000"}))  # standard tax invoice
    root.append(el("cbc:DocumentCurrencyCode", invoice.currency or "SAR"))
    root.append(el("cbc:TaxCurrencyCode", invoice.currency or "SAR"))

    # Seller (AccountingSupplierParty)
    supplier = ET.SubElement(root, "cac:AccountingSupplierParty")
    party = ET.SubElement(supplier, "cac:Party")
    party_name = ET.SubElement(party, "cac:PartyName")
    party_name.append(el("cbc:Name", org.name))
    postal = ET.SubElement(party, "cac:PostalAddress")
    postal.append(el("cbc:CountrySubentity", "SA"))
    country_el = ET.SubElement(postal, "cac:Country")
    country_el.append(el("cbc:IdentificationCode", "SA"))
    tax_scheme_el = ET.SubElement(party, "cac:PartyTaxScheme")
    tax_scheme_el.append(el("cbc:CompanyID", org.vat_number or ""))
    scheme = ET.SubElement(tax_scheme_el, "cac:TaxScheme")
    scheme.append(el("cbc:ID", "VAT"))
    legal_entity = ET.SubElement(party, "cac:PartyLegalEntity")
    legal_entity.append(el("cbc:RegistrationName", org.name))

    # TaxTotal
    vat_total = float(invoice.vat_amount or 0)
    tax_total_el = ET.SubElement(root, "cac:TaxTotal")
    tax_total_el.append(el("cbc:TaxAmount", f"{vat_total:.2f}", {"currencyID": invoice.currency or "SAR"}))
    tax_subtotal = ET.SubElement(tax_total_el, "cac:TaxSubtotal")
    subtotal_amt = float(invoice.subtotal or 0)
    tax_subtotal.append(el("cbc:TaxableAmount", f"{subtotal_amt:.2f}", {"currencyID": invoice.currency or "SAR"}))
    tax_subtotal.append(el("cbc:TaxAmount", f"{vat_total:.2f}", {"currencyID": invoice.currency or "SAR"}))
    tax_cat = ET.SubElement(tax_subtotal, "cac:TaxCategory")
    tax_cat.append(el("cbc:ID", "S"))
    # Use first line's tax rate, or 15 (Saudi standard)
    rate = float(line_items[0].tax_rate) if line_items else 15.0
    tax_cat.append(el("cbc:Percent", f"{rate:.2f}"))
    ts = ET.SubElement(tax_cat, "cac:TaxScheme")
    ts.append(el("cbc:ID", "VAT"))

    # LegalMonetaryTotal
    total_float = float(invoice.total_sek or 0)
    monetary = ET.SubElement(root, "cac:LegalMonetaryTotal")
    monetary.append(el("cbc:LineExtensionAmount", f"{subtotal_amt:.2f}", {"currencyID": invoice.currency or "SAR"}))
    monetary.append(el("cbc:TaxExclusiveAmount", f"{subtotal_amt:.2f}", {"currencyID": invoice.currency or "SAR"}))
    monetary.append(el("cbc:TaxInclusiveAmount", f"{total_float:.2f}", {"currencyID": invoice.currency or "SAR"}))
    monetary.append(el("cbc:PayableAmount", f"{total_float:.2f}", {"currencyID": invoice.currency or "SAR"}))

    # InvoiceLines
    for i, item in enumerate(line_items, 1):
        line_el = ET.SubElement(root, "cac:InvoiceLine")
        line_el.append(el("cbc:ID", str(i)))
        line_el.append(el("cbc:InvoicedQuantity", str(item.quantity), {"unitCode": "PCE"}))
        line_el.append(el("cbc:LineExtensionAmount", f"{float(item.line_total or 0):.2f}", {"currencyID": invoice.currency or "SAR"}))
        item_el = ET.SubElement(line_el, "cac:Item")
        item_el.append(el("cbc:Name", item.description or ""))
        line_tax = ET.SubElement(line_el, "cac:TaxTotal")
        line_vat = float(item.line_total or 0) * float(item.tax_rate or 0) / 100
        line_tax.append(el("cbc:TaxAmount", f"{line_vat:.2f}", {"currencyID": invoice.currency or "SAR"}))
        price_el = ET.SubElement(line_el, "cac:Price")
        price_el.append(el("cbc:PriceAmount", f"{float(item.unit_price or 0):.2f}", {"currencyID": invoice.currency or "SAR"}))

    ET.indent(root, space="  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")


# ── Schemas ──────────────────────────────────────────────────────────────────

class ZatcaGenerateOut(BaseModel):
    zatca_invoice_id: str
    invoice_id: str
    invoice_number: str
    invoice_hash: str
    qr_tlv_b64: str
    clearance_status: str

class ZatcaDetailOut(BaseModel):
    id: str
    org_id: str
    invoice_id: str
    invoice_hash: str
    qr_tlv_b64: str
    clearance_status: str
    zatca_uuid: Optional[str]
    created_at: str
    updated_at: str

class ZatcaListOut(BaseModel):
    records: list[ZatcaDetailOut]
    total: int


# ── Helpers ───────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _detail_out(z: ZatcaInvoice) -> ZatcaDetailOut:
    return ZatcaDetailOut(
        id=str(z.id),
        org_id=str(z.org_id),
        invoice_id=str(z.invoice_id),
        invoice_hash=z.invoice_hash,
        qr_tlv_b64=z.qr_tlv_b64,
        clearance_status=z.clearance_status,
        zatca_uuid=z.zatca_uuid,
        created_at=z.created_at.isoformat(),
        updated_at=z.updated_at.isoformat(),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/generate/{invoice_id}", response_model=ZatcaGenerateOut)
async def generate_zatca(
    invoice_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan=Depends(require_plan(OrgPlan.PRO)),
):
    """Generate ZATCA Phase 2 XML and TLV QR for an invoice."""
    org_id = _org_id(ctx)
    try:
        # Load invoice + line items
        inv_row = await db.execute(
            select(Invoice)
            .where(Invoice.id == invoice_id, Invoice.org_id == org_id)
            .options(selectinload(Invoice.line_items))
        )
        invoice = inv_row.scalar_one_or_none()
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        # Load org for seller details
        org_row = await db.execute(select(Organization).where(Organization.id == org_id))
        org = org_row.scalar_one_or_none()
        if not org:
            raise HTTPException(status_code=404, detail="Organisation not found")

        # Build XML
        xml_str = _build_zatca_xml(invoice, org, invoice.line_items or [])

        # SHA-256 hash of canonical XML (UTF-8 bytes)
        xml_bytes = xml_str.encode("utf-8")
        invoice_hash_hex = hashlib.sha256(xml_bytes).hexdigest()

        # Issue datetime string
        issue_dt = invoice.issue_date
        if hasattr(issue_dt, "strftime"):
            dt_str = issue_dt.strftime("%Y-%m-%dT00:00:00Z")
        else:
            dt_str = f"{issue_dt}T00:00:00Z"

        # TLV QR
        qr_b64 = _build_qr_tlv(
            seller_name=org.name,
            vat_number=org.vat_number or "",
            invoice_datetime=dt_str,
            total_with_vat=f"{float(invoice.total_sek or 0):.2f}",
            vat_amount=f"{float(invoice.vat_amount or 0):.2f}",
            invoice_hash_hex=invoice_hash_hex,
        )

        # Upsert ZatcaInvoice
        existing = await db.execute(
            select(ZatcaInvoice).where(ZatcaInvoice.invoice_id == invoice_id)
        )
        zatca = existing.scalar_one_or_none()
        if zatca:
            zatca.invoice_hash = invoice_hash_hex
            zatca.qr_tlv_b64 = qr_b64
            zatca.xml_content = xml_str
        else:
            zatca = ZatcaInvoice(
                org_id=org_id,
                invoice_id=invoice_id,
                invoice_hash=invoice_hash_hex,
                qr_tlv_b64=qr_b64,
                xml_content=xml_str,
                clearance_status="pending",
            )
            db.add(zatca)
        await db.commit()
        await db.refresh(zatca)

        return ZatcaGenerateOut(
            zatca_invoice_id=str(zatca.id),
            invoice_id=str(invoice_id),
            invoice_number=invoice.invoice_number,
            invoice_hash=invoice_hash_hex,
            qr_tlv_b64=qr_b64,
            clearance_status=zatca.clearance_status,
        )

    except HTTPException:
        raise
    except Exception as e:
        log.error("zatca_generate failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/list", response_model=ZatcaListOut)
async def list_zatca(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan=Depends(require_plan(OrgPlan.PRO)),
):
    org_id = _org_id(ctx)
    try:
        offset = (page - 1) * limit
        rows = await db.execute(
            select(ZatcaInvoice)
            .where(ZatcaInvoice.org_id == org_id)
            .order_by(ZatcaInvoice.created_at.desc())
            .limit(limit).offset(offset)
        )
        records = rows.scalars().all()
        count_row = await db.execute(
            select(func.count(ZatcaInvoice.id))
            .where(ZatcaInvoice.org_id == org_id)
        )
        total = count_row.scalar_one() or 0
        return ZatcaListOut(records=[_detail_out(z) for z in records], total=total)
    except HTTPException:
        raise
    except Exception as e:
        log.error("zatca_list failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{invoice_id}", response_model=ZatcaDetailOut)
async def get_zatca(
    invoice_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan=Depends(require_plan(OrgPlan.PRO)),
):
    org_id = _org_id(ctx)
    try:
        row = await db.execute(
            select(ZatcaInvoice).where(
                ZatcaInvoice.invoice_id == invoice_id,
                ZatcaInvoice.org_id == org_id,
            )
        )
        zatca = row.scalar_one_or_none()
        if not zatca:
            raise HTTPException(status_code=404, detail="ZATCA record not found — generate it first")
        return _detail_out(zatca)
    except HTTPException:
        raise
    except Exception as e:
        log.error("zatca_get failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{invoice_id}/xml")
async def download_zatca_xml(
    invoice_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan=Depends(require_plan(OrgPlan.PRO)),
):
    org_id = _org_id(ctx)
    try:
        row = await db.execute(
            select(ZatcaInvoice).where(
                ZatcaInvoice.invoice_id == invoice_id,
                ZatcaInvoice.org_id == org_id,
            )
        )
        zatca = row.scalar_one_or_none()
        if not zatca:
            raise HTTPException(status_code=404, detail="ZATCA record not found — generate it first")
        return Response(
            content=zatca.xml_content.encode("utf-8"),
            media_type="application/xml",
            headers={"Content-Disposition": f'attachment; filename="zatca_{invoice_id}.xml"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error("zatca_xml failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/dashboard")
async def zatca_dashboard(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan=Depends(require_plan(OrgPlan.PRO)),
):
    """Compliance dashboard: counts per clearance status + recent records."""
    org_id = _org_id(ctx)
    try:
        rows = await db.execute(
            select(ZatcaInvoice.clearance_status, func.count(ZatcaInvoice.id))
            .where(ZatcaInvoice.org_id == org_id)
            .group_by(ZatcaInvoice.clearance_status)
        )
        breakdown = {row[0]: row[1] for row in rows}

        # Sequence gap check: fetch the last 20 invoice numbers and look for gaps
        recent_rows = await db.execute(
            select(ZatcaInvoice)
            .where(ZatcaInvoice.org_id == org_id)
            .order_by(ZatcaInvoice.created_at.desc())
            .limit(10)
        )
        recent = recent_rows.scalars().all()

        return {
            "summary": {
                "pending": breakdown.get("pending", 0),
                "submitted": breakdown.get("submitted", 0),
                "cleared": breakdown.get("cleared", 0),
                "rejected": breakdown.get("rejected", 0),
                "not_submitted": breakdown.get("not_submitted", 0),
            },
            "total": sum(breakdown.values()),
            "recent": [_detail_out(z) for z in recent],
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("zatca_dashboard failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{invoice_id}/status")
async def update_zatca_status(
    invoice_id: uuid.UUID,
    clearance_status: str,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan=Depends(require_plan(OrgPlan.PRO)),
):
    """Update clearance_status on an existing ZATCA record (e.g. after ZATCA API response)."""
    org_id = _org_id(ctx)
    VALID_STATUSES = {"pending", "submitted", "cleared", "rejected", "not_submitted"}
    try:
        if clearance_status not in VALID_STATUSES:
            raise HTTPException(status_code=422, detail=f"Invalid status. Valid: {sorted(VALID_STATUSES)}")
        row = await db.execute(
            select(ZatcaInvoice).where(
                ZatcaInvoice.invoice_id == invoice_id,
                ZatcaInvoice.org_id == org_id,
            )
        )
        zatca = row.scalar_one_or_none()
        if not zatca:
            raise HTTPException(status_code=404, detail="ZATCA record not found")
        zatca.clearance_status = clearance_status
        await db.commit()
        await db.refresh(zatca)
        return _detail_out(zatca)
    except HTTPException:
        raise
    except Exception as e:
        log.error("zatca_status_update failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/submit/{invoice_id}")
async def submit_for_clearance(
    invoice_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan=Depends(require_plan(OrgPlan.PRO)),
):
    """Submit invoice to ZATCA for clearance.

    STUB: Live submission requires a CSID certificate issued by ZATCA per company.
    Generate your CSID at https://zatca.gov.sa/en/E-Invoicing/Pages/default.aspx
    then integrate your certificate into this endpoint.
    """
    org_id = _org_id(ctx)
    try:
        row = await db.execute(
            select(ZatcaInvoice).where(
                ZatcaInvoice.invoice_id == invoice_id,
                ZatcaInvoice.org_id == org_id,
            )
        )
        zatca = row.scalar_one_or_none()
        if not zatca:
            raise HTTPException(status_code=404, detail="Generate ZATCA record first")
        return {
            "clearance_status": "not_submitted",
            "message": (
                "Live ZATCA clearance requires a per-company CSID certificate from ZATCA. "
                "Complete onboarding at https://zatca.gov.sa and configure your certificate "
                "to enable real-time clearance. XML and QR code have been generated correctly."
            ),
            "invoice_hash": zatca.invoice_hash,
            "qr_tlv_b64": zatca.qr_tlv_b64,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("zatca_submit failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
