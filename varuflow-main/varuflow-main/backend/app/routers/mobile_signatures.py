"""Digital signature capture

Captures SVG path data from an on-device signature pad and links it
to a document (delivery_note | contract | invoice | other).

Endpoints:
  POST /api/mobile/signatures
  GET  /api/mobile/signatures
  GET  /api/mobile/signatures/{id}
  DELETE /api/mobile/signatures/{id}
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

import io
import base64

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.mobile_field import DigitalSignature

router = APIRouter(prefix="/api/mobile/signatures", tags=["mobile_signatures"])
log = logging.getLogger(__name__)


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Schemas ───────────────────────────────────────────────────────────────────

class SignatureIn(BaseModel):
    signer_name: str
    signer_role: Optional[str] = None
    document_type: str = "delivery_note"     # delivery_note|contract|invoice|other
    ref_id: Optional[uuid.UUID] = None
    svg_data: str                            # SVG path element content, e.g. "M 10 20 L 30 40 ..."

class SignatureOut(BaseModel):
    id: str
    signer_name: str
    signer_role: Optional[str]
    document_type: str
    ref_id: Optional[str]
    svg_data: str
    ip_address: Optional[str]
    signed_at: str

class SignaturesOut(BaseModel):
    signatures: list[SignatureOut]
    total: int


def _out(s: DigitalSignature) -> SignatureOut:
    return SignatureOut(
        id=str(s.id),
        signer_name=s.signer_name,
        signer_role=s.signer_role,
        document_type=s.document_type,
        ref_id=str(s.ref_id) if s.ref_id else None,
        svg_data=s.svg_data,
        ip_address=s.ip_address,
        signed_at=s.signed_at.isoformat(),
    )


VALID_DOC_TYPES = {"delivery_note", "contract", "invoice", "other"}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", response_model=SignatureOut)
async def capture_signature(
    body: SignatureIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        if body.document_type not in VALID_DOC_TYPES:
            raise HTTPException(status_code=422, detail=f"document_type must be one of {VALID_DOC_TYPES}")
        if not body.svg_data.strip():
            raise HTTPException(status_code=422, detail="svg_data cannot be empty")
        # Cap SVG data at 200 KB to prevent abuse
        if len(body.svg_data.encode()) > 204_800:
            raise HTTPException(status_code=422, detail="svg_data exceeds 200 KB limit")

        # Extract real client IP (honour X-Forwarded-For on Railway)
        forwarded = request.headers.get("X-Forwarded-For")
        ip_address = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else None)

        sig = DigitalSignature(
            org_id=org_id,
            signer_name=body.signer_name,
            signer_role=body.signer_role,
            document_type=body.document_type,
            ref_id=body.ref_id,
            svg_data=body.svg_data,
            ip_address=ip_address,
        )
        db.add(sig)
        await db.commit()
        await db.refresh(sig)
        return _out(sig)
    except HTTPException:
        raise
    except Exception as e:
        log.error("capture_signature failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("", response_model=SignaturesOut)
async def list_signatures(
    document_type: Optional[str] = Query(None),
    ref_id: Optional[uuid.UUID] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        q = select(DigitalSignature).where(DigitalSignature.org_id == org_id)
        if document_type:
            q = q.where(DigitalSignature.document_type == document_type)
        if ref_id:
            q = q.where(DigitalSignature.ref_id == ref_id)

        count_row = await db.execute(
            select(func.count(DigitalSignature.id)).where(DigitalSignature.org_id == org_id)
        )
        total = count_row.scalar_one() or 0
        rows = await db.execute(q.order_by(DigitalSignature.signed_at.desc()).limit(limit).offset((page - 1) * limit))
        return SignaturesOut(signatures=[_out(s) for s in rows.scalars()], total=total)
    except Exception as e:
        log.error("list_signatures failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{sig_id}", response_model=SignatureOut)
async def get_signature(
    sig_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        row = await db.execute(
            select(DigitalSignature).where(DigitalSignature.id == sig_id, DigitalSignature.org_id == org_id)
        )
        sig = row.scalar_one_or_none()
        if not sig:
            raise HTTPException(status_code=404, detail="Signature not found")
        return _out(sig)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_signature failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{sig_id}")
async def delete_signature(
    sig_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        row = await db.execute(
            select(DigitalSignature).where(DigitalSignature.id == sig_id, DigitalSignature.org_id == org_id)
        )
        sig = row.scalar_one_or_none()
        if not sig:
            raise HTTPException(status_code=404, detail="Signature not found")
        await db.delete(sig)
        await db.commit()
        return {"deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_signature failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{sig_id}/pdf")
async def signature_pdf(
    sig_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Generate a PDF certificate for a captured signature."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as rl_canvas

    org_id = _org(ctx)
    try:
        row = await db.execute(
            select(DigitalSignature).where(DigitalSignature.id == sig_id, DigitalSignature.org_id == org_id)
        )
        sig = row.scalar_one_or_none()
        if not sig:
            raise HTTPException(status_code=404, detail="Signature not found")

        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=A4)
        w, h = A4

        # Header
        c.setFont("Helvetica-Bold", 16)
        c.drawString(20 * mm, h - 20 * mm, "Digital Signature Certificate")
        c.setFont("Helvetica", 10)
        c.drawString(20 * mm, h - 28 * mm, f"Signer: {sig.signer_name}")
        if sig.signer_role:
            c.drawString(20 * mm, h - 34 * mm, f"Role: {sig.signer_role}")
        c.drawString(20 * mm, h - 40 * mm, f"Document type: {sig.document_type}")
        c.drawString(20 * mm, h - 46 * mm, f"Signed at: {sig.signed_at.isoformat()}")
        if sig.ip_address:
            c.drawString(20 * mm, h - 52 * mm, f"IP address: {sig.ip_address}")
        if sig.ref_id:
            c.drawString(20 * mm, h - 58 * mm, f"Reference ID: {sig.ref_id}")

        # Signature image — support base64 PNG data URL or raw base64
        svg_data = sig.svg_data or ""
        img_y = h - 150 * mm
        if svg_data.startswith("data:image/png;base64,"):
            raw_b64 = svg_data.split(",", 1)[1]
            img_bytes = base64.b64decode(raw_b64)
            img_buf = io.BytesIO(img_bytes)
            from reportlab.lib.utils import ImageReader
            img_reader = ImageReader(img_buf)
            c.drawImage(img_reader, 20 * mm, img_y, width=160 * mm, height=60 * mm, preserveAspectRatio=True)
        else:
            # Fall back: render SVG path instruction as text
            c.setFont("Courier", 8)
            c.drawString(20 * mm, img_y + 10 * mm, "[Signature data — render in SVG viewer]")

        # Border around signature area
        c.rect(20 * mm, img_y, 160 * mm, 60 * mm)

        # Footer
        c.setFont("Helvetica-Oblique", 8)
        c.setFillColorRGB(0.5, 0.5, 0.5)
        c.drawString(20 * mm, 15 * mm, "This certificate is generated by Varuflow and constitutes a digital record of the above signature.")

        c.save()
        buf.seek(0)

        filename = f"signature-{sig_id}.pdf"
        return StreamingResponse(
            buf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error("signature_pdf failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")

