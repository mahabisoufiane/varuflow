"""Bulk product import router (Item 69).

Endpoint:

    POST /api/inventory/products/bulk-import

Accepts a CSV document (as JSON ``{"csv": "..."}``) and either creates
new products or updates existing ones by SKU. Only OWNER / ADMIN roles
may trigger a bulk import — the feature rewrites pricing catalogues and
must not be reachable by seasonal staff.

The endpoint returns a per-row breakdown:

    {
        "created": 12,
        "updated":  3,
        "errors": [
            {"line": 5, "field": null, "message": "sku is required"},
            {"line": 9, "field": "sku", "message": "duplicate sku in file: A1"}
        ]
    }

One ``product.bulk_imported`` audit log entry is emitted with the
same counts in ``extra`` so the activity feed surfaces imports.
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.inventory import Product
from app.models.organization import OrgRole, Organization
from app.services import product_import as svc_69
from app.services.audit import log_action
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/inventory", tags=["inventory"], dependencies=[Depends(require_module("inventory"))])

log = logging.getLogger(__name__)


class BulkImportRequest(BaseModel):
    csv: str = Field(..., description="CSV document (UTF-8, comma-delimited)")


class BulkImportError(BaseModel):
    line:    int
    field:   Optional[str] = None
    message: str


class BulkImportResult(BaseModel):
    created: int
    updated: int
    errors:  list[BulkImportError]


@router.post(
    "/products/bulk-import",
    response_model=BulkImportResult,
    status_code=status.HTTP_200_OK,
)
async def bulk_import_products(
    body:    BulkImportRequest,
    request: Request,
    ctx:     tuple = Depends(get_current_member),
    db:      AsyncSession = Depends(get_db),
) -> BulkImportResult:
    user, member = ctx
    if member.role not in (OrgRole.OWNER, OrgRole.ADMIN):
        raise HTTPException(
            status_code=403,
            detail="Only OWNER/ADMIN may bulk-import products",
        )

    # Parse + validate every row in isolation. This is a pure function;
    # nothing hits the DB until we know which rows are structurally
    # valid, which keeps the transaction tight.
    parsed = svc_69.parse_csv(body.csv)

    # Serialise on the org row so concurrent bulk-imports against the
    # same tenant cannot both see the same "existing" SKU set and then
    # both INSERT. Matches the locking pattern in create_product.
    await db.execute(
        select(Organization.id)
        .where(Organization.id == member.org_id)
        .with_for_update()
    )

    # Resolve which SKUs already exist for this tenant so we can
    # classify rows as insert vs. update.
    sku_values = [r.sku for r in parsed.rows]
    existing_map: dict[str, Product] = {}
    if sku_values:
        rows = await db.execute(
            select(Product).where(
                Product.org_id == member.org_id,
                Product.sku.in_(sku_values),
            )
        )
        for p in rows.scalars().all():
            existing_map[p.sku] = p

    created = 0
    updated = 0
    for row in parsed.rows:
        existing = existing_map.get(row.sku)
        if existing is None:
            db.add(
                Product(
                    org_id=member.org_id,
                    sku=row.sku,
                    name=row.name,
                    category=row.category,
                    unit=row.unit,
                    purchase_price=row.purchase_price,
                    sell_price=row.sell_price,
                    tax_rate=row.tax_rate,
                    barcode=row.barcode,
                    description=row.description,
                    reorder_level=row.reorder_level,
                )
            )
            created += 1
        else:
            existing.name = row.name
            existing.category = row.category
            existing.unit = row.unit
            existing.purchase_price = row.purchase_price
            existing.sell_price = row.sell_price
            existing.tax_rate = row.tax_rate
            existing.barcode = row.barcode
            existing.description = row.description
            existing.reorder_level = row.reorder_level
            updated += 1

    await db.flush()

    await log_action(
        db,
        action="product.bulk_imported",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="product_batch",
        target_id=str(uuid.uuid4()),
        request=request,
        extra={
            "created": created,
            "updated": updated,
            "errors":  len(parsed.errors),
        },
    )
    await db.commit()

    return BulkImportResult(
        created=created,
        updated=updated,
        errors=[
            BulkImportError(line=e.line, field=e.field, message=e.message)
            for e in parsed.errors
        ],
    )
