"""Barcode / QR label printing router (Item 36).

Endpoint map
------------
    GET  /api/labels/sizes                   — supported sizes + label count per sheet
    POST /api/labels/print                   — render PDF for 1..N products by id
    POST /api/labels/print/custom            — render PDF for ad-hoc label dicts
                                               (e.g. unregistered inventory, lot labels)
    POST /api/labels/print/single/{product_id}
                                             — one-tap mobile endpoint for a single
                                               product; no request body required

All label-generation actions write an audit row so staff can track
who printed what (compliance requirement for regulated SKUs).
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.inventory import Product
from app.services.audit import log_action
from app.services.label_generator import (
    LABEL_SIZES,
    LabelOptions,
    generate_label_pdf,
    labels_per_sheet,
    validate_format,
    validate_size,
)
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/labels", tags=["labels"], dependencies=[Depends(require_module("inventory"))])


# ── Schemas ───────────────────────────────────────────────────────


class LabelSizeOut(BaseModel):
    size: str
    label_width_mm: float
    label_height_mm: float
    labels_per_sheet: int


class PrintRequest(BaseModel):
    product_ids: list[uuid.UUID] = Field(default_factory=list, max_length=500)
    size: str = Field("50x30", min_length=2, max_length=16)
    format: str = Field("code128", min_length=2, max_length=16)
    show_price: bool = True
    show_logo: bool = False
    currency: str = Field("kr", min_length=1, max_length=8)
    # Optional repeat: e.g. "print 12 copies of each selected label".
    copies_per_product: int = Field(1, ge=1, le=100)


class CustomLabelEntry(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    sku: str = Field(..., min_length=1, max_length=60)
    barcode: str | None = Field(None, max_length=120)
    price: Decimal | None = None


class CustomPrintRequest(BaseModel):
    labels: list[CustomLabelEntry] = Field(..., min_length=1, max_length=500)
    size: str = "50x30"
    format: str = "code128"
    show_price: bool = True
    show_logo: bool = False
    currency: str = "kr"


# ── Helpers ───────────────────────────────────────────────────────


def _pdf_response(pdf_bytes: bytes, filename: str) -> Response:
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


async def _fetch_products(
    db: AsyncSession, *, org_id: uuid.UUID, ids: list[uuid.UUID]
) -> list[Product]:
    if not ids:
        return []
    stmt = select(Product).where(
        Product.org_id == org_id,
        Product.id.in_(ids),
    )
    rows = (await db.execute(stmt)).scalars().all()
    # Preserve the caller's order (UI expects printed order = selected order).
    by_id = {p.id: p for p in rows}
    return [by_id[i] for i in ids if i in by_id]


def _product_to_label(product: Product) -> dict:
    return {
        "name": product.name,
        "sku": product.sku,
        "barcode": product.barcode or product.sku,
        "price": product.sell_price,
    }


# ── Endpoints ─────────────────────────────────────────────────────


@router.get("/sizes", response_model=list[LabelSizeOut])
async def get_sizes(ctx: tuple = Depends(get_current_member)):
    """Supported label stocks with their physical dimensions."""
    out: list[LabelSizeOut] = []
    for key, (_, _, cols, rows, w_mm, h_mm) in LABEL_SIZES.items():
        out.append(LabelSizeOut(
            size=key,
            label_width_mm=w_mm,
            label_height_mm=h_mm,
            labels_per_sheet=cols * rows,
        ))
    return out


@router.post("/print")
async def print_labels(
    body: PrintRequest,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    try:
        size = validate_size(body.size)
        fmt = validate_format(body.format)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    if not body.product_ids:
        raise HTTPException(status_code=422, detail="no_products_selected")

    products = await _fetch_products(db, org_id=member.org_id, ids=body.product_ids)
    if not products:
        # Every selected id was either missing or owned by another
        # org — treat as 404 so the UI can surface "no products found".
        raise HTTPException(status_code=404, detail="products_not_found")

    labels: list[dict] = []
    for product in products:
        entry = _product_to_label(product)
        labels.extend([entry] * max(1, body.copies_per_product))

    opts = LabelOptions(
        size=size,  # type: ignore[arg-type]
        format=fmt,  # type: ignore[arg-type]
        show_price=body.show_price,
        show_logo=body.show_logo,
        currency=body.currency,
    )
    pdf = generate_label_pdf(labels, opts)

    await log_action(
        db,
        action="labels.generated",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="inventory",
        target_id=None,
        request=request,
        extra={
            "product_count": len(products),
            "label_count": len(labels),
            "size": size,
            "format": fmt,
            "show_price": body.show_price,
            "copies_per_product": body.copies_per_product,
        },
    )
    await db.commit()

    filename = f"labels-{size}-{len(labels)}.pdf"
    return _pdf_response(pdf, filename)


@router.post("/print/custom")
async def print_custom_labels(
    body: CustomPrintRequest,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Print ad-hoc labels that aren't tied to a saved Product row.

    Used for lot markers, warehouse bin labels, or freshly received
    stock that hasn't been catalogued yet.
    """
    user, member = ctx
    try:
        size = validate_size(body.size)
        fmt = validate_format(body.format)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    labels = [
        {
            "name": lbl.name,
            "sku": lbl.sku,
            "barcode": lbl.barcode or lbl.sku,
            "price": lbl.price,
        }
        for lbl in body.labels
    ]
    opts = LabelOptions(
        size=size,  # type: ignore[arg-type]
        format=fmt,  # type: ignore[arg-type]
        show_price=body.show_price,
        show_logo=body.show_logo,
        currency=body.currency,
    )
    pdf = generate_label_pdf(labels, opts)

    await log_action(
        db,
        action="labels.generated_custom",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="inventory",
        target_id=None,
        request=request,
        extra={"label_count": len(labels), "size": size, "format": fmt},
    )
    await db.commit()

    filename = f"labels-custom-{size}-{len(labels)}.pdf"
    return _pdf_response(pdf, filename)


@router.post("/print/single/{product_id}")
async def print_single_label(
    product_id: uuid.UUID,
    request: Request,
    size: str = Query("38x25"),
    format: str = Query("code128"),
    show_price: bool = Query(True),
    currency: str = Query("kr"),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Mobile-friendly single-label endpoint.

    Query-params so the trigger can be a plain link / button tap from
    a phone browser, no form body required. Defaults to the smallest
    thermal stock (38×25) since that's what mobile shelves typically
    use.
    """
    user, member = ctx
    try:
        size_key = validate_size(size)
        fmt_key = validate_format(format)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    products = await _fetch_products(db, org_id=member.org_id, ids=[product_id])
    if not products:
        raise HTTPException(status_code=404, detail="product_not_found")
    product = products[0]

    opts = LabelOptions(
        size=size_key,  # type: ignore[arg-type]
        format=fmt_key,  # type: ignore[arg-type]
        show_price=show_price,
        show_logo=False,
        currency=currency,
    )
    pdf = generate_label_pdf([_product_to_label(product)], opts)

    await log_action(
        db,
        action="labels.generated_single",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="product",
        target_id=str(product.id),
        request=request,
        extra={"size": size_key, "format": fmt_key},
    )
    await db.commit()

    filename = f"label-{product.sku}.pdf"
    return _pdf_response(pdf, filename)
