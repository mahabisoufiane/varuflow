"""Inventory module: products, warehouses, stock, movements, suppliers, POs."""
import csv
import io
import logging
import uuid
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status

log = logging.getLogger(__name__)
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.features.auth.organization import Organization
from .models import (
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatus,
    StockLevel,
    StockMovement,
    StockMovementType,
    Supplier,
    Warehouse,
)
from app.schemas.inventory import (
    CSVImportResult,
    DemandForecastOut,
    PaginatedProducts,
    ProductCreate,
    ProductOut,
    ProductUpdate,
    PurchaseOrderCreate,
    PurchaseOrderOut,
    PurchaseOrderStatusUpdate,
    StockLevelOut,
    StockMovementCreate,
    StockMovementOut,
    StockThresholdUpdate,
    SupplierCreate,
    SupplierOut,
    SupplierUpdate,
    WarehouseCreate,
    WarehouseOut,
    WarehouseUpdate,
)
from app.services.pdf_generator import generate_purchase_order_pdf
from app.services.plan_limits import (
    RESOURCE_PRODUCTS,
    RESOURCE_WAREHOUSES,
    LimitExceededError,
    check_limit,
)
from app.features.compliance.audit_models import AuditLogEntry

router = APIRouter(prefix="/api/inventory", tags=["inventory"], dependencies=[Depends(require_module("inventory"))])


def _org(ctx: tuple) -> uuid.UUID:
    """Extract org_id from get_current_member context."""
    _, member = ctx
    return member.org_id


# ── Products ──────────────────────────────────────────────────────────────────

@router.get("/products", response_model=PaginatedProducts)
async def list_products(
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        q = select(Product).where(Product.org_id == org_id)
        if search:
            like = f"%{search}%"
            q = q.where(Product.name.ilike(like) | Product.sku.ilike(like))
        if category:
            q = q.where(Product.category == category)
        if is_active is not None:
            q = q.where(Product.is_active == is_active)

        total_result = await db.execute(select(func.count()).select_from(q.subquery()))
        total = total_result.scalar_one()

        q = q.order_by(Product.name).offset(skip).limit(limit)
        result = await db.execute(q)
        items = result.scalars().all()
        return PaginatedProducts(items=items, total=total, skip=skip, limit=limit)
    except HTTPException:
        raise
    except Exception as e:
        log.error("list_products failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(
    body: ProductCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    # ── Plan limit: max products ───────────────────────────────────────────────
    _org_plan = await db.scalar(select(Organization.plan).where(Organization.id == org_id))
    _product_count = await db.scalar(
        select(func.count()).select_from(Product).where(Product.org_id == org_id)
    ) or 0
    try:
        check_limit(_org_plan, RESOURCE_PRODUCTS, _product_count)
    except LimitExceededError as _exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "PLAN_LIMIT_EXCEEDED",
                "resource": RESOURCE_PRODUCTS,
                "limit": _exc.limit,
                "current": _exc.current,
            },
        )
    # ──────────────────────────────────────────────────────────────────────────
    # Serialise on the org row so two simultaneous POSTs with the same SKU
    # cannot both pass the existence check and both INSERT. The Product
    # table intentionally has no DB-level UNIQUE(org_id, sku) constraint
    # (see models/inventory.py — kept absent to tolerate legacy duplicate
    # rows), so without this lock the race lands two products with the
    # same (org_id, sku) and every subsequent lookup that uses
    # `db.scalar()` to resolve a product by SKU (CSV upsert,
    # update_product collision check, this endpoint) raises
    # MultipleResultsFound → 500.
    from app.features.auth.organization import Organization as _Organization
    await db.execute(
        select(_Organization.id).where(_Organization.id == org_id).with_for_update()
    )
    existing = await db.scalar(
        select(Product.id).where(Product.org_id == org_id, Product.sku == body.sku).limit(1)
    )
    if existing:
        raise HTTPException(status_code=409, detail=f"SKU '{body.sku}' already exists")
    product = Product(org_id=org_id, **body.model_dump())
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


@router.get("/products/{product_id}", response_model=ProductOut)
async def get_product(
    product_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        product = await db.scalar(
            select(Product).where(Product.id == product_id, Product.org_id == org_id)
        )
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return product
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_product failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/products/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: uuid.UUID,
    body: ProductUpdate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    product = await db.scalar(
        select(Product).where(Product.id == product_id, Product.org_id == org_id)
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    updates = body.model_dump(exclude_unset=True)
    # Reject SKU rename if it would collide with another product in the same
    # org. Without a DB-level UNIQUE(org_id, sku) constraint (see
    # models/inventory.py — intentionally absent to tolerate legacy duplicates),
    # nothing else prevents this, and a collision breaks every lookup that
    # resolves a product by (org_id, sku) — notably the CSV upsert and
    # `create_product`'s `.scalar()` pre-check, which then raises
    # MultipleResultsFound and 500s the caller.
    new_sku = updates.get("sku")
    if new_sku is not None and new_sku != product.sku:
        # .limit(1) is required because the Product table intentionally
        # has no UNIQUE(org_id, sku) constraint (see the comment in
        # create_product / models/inventory.py — kept absent to tolerate
        # legacy duplicate rows). Without the cap, two or more existing
        # rows already sharing `new_sku` would make `db.scalar()` raise
        # MultipleResultsFound and 500 the caller — exactly the failure
        # mode the duplicate-tolerance design was meant to avoid.
        clash = await db.scalar(
            select(Product.id).where(
                Product.org_id == org_id,
                Product.sku == new_sku,
                Product.id != product_id,
            ).limit(1)
        )
        if clash:
            raise HTTPException(
                status_code=409, detail=f"SKU '{new_sku}' already exists"
            )
    for k, v in updates.items():
        setattr(product, k, v)
    await db.commit()
    await db.refresh(product)
    return product


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    product = await db.scalar(
        select(Product).where(Product.id == product_id, Product.org_id == _org(ctx))
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    product.is_active = False
    _, member = ctx
    db.add(AuditLogEntry(
        org_id=member.org_id,
        actor_user_id=member.user_id,
        action="inventory.product_deleted",
        target_type="product",
        target_id=str(product_id),
        extra={"name": product.name, "sku": product.sku},
    ))
    await db.commit()


@router.post("/products/import", response_model=CSVImportResult)
async def import_products_csv(
    file: UploadFile = File(...),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Bulk import products from a CSV file.

    Expected columns: name, sku, category, unit, purchase_price, sell_price, tax_rate

    Hard limits (DoS guard):
      • Max size:   5 MB — enough for ~50 000 rows of typical SKU data
      • Content-Type must declare CSV (browsers send `text/csv` or
        `application/vnd.ms-excel`) — blocks accidental binary uploads.
      • Row cap: 50 000 rows to bound memory + commit time.
    """
    MAX_BYTES = 5 * 1024 * 1024
    ALLOWED_CT = {"text/csv", "application/csv", "application/vnd.ms-excel", "text/plain"}
    MAX_ROWS = 50_000

    ct = (file.content_type or "").split(";")[0].strip().lower()
    if ct and ct not in ALLOWED_CT:
        raise HTTPException(status_code=415, detail=f"Unsupported content type: {ct}")

    # Early size check using declared Content-Length / file.size when available.
    # Avoids reading the body into memory for obvious DoS attempts.
    declared_size = getattr(file, "size", None)
    if declared_size is not None and declared_size > MAX_BYTES:
        raise HTTPException(status_code=413, detail="CSV file exceeds 5 MB limit")

    org_id = _org(ctx)
    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="CSV file exceeds 5 MB limit")

    try:
        text_content = content.decode("utf-8-sig")  # handle BOM
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File is not valid UTF-8 CSV")

    reader = csv.DictReader(io.StringIO(text_content))

    created = updated = 0
    errors: list[str] = []
    # Cap the error list to keep the response bounded even if every row is
    # malformed. Clients only need a representative sample to fix their file.
    MAX_ERRORS = 100

    def _record_error(msg: str) -> None:
        if len(errors) < MAX_ERRORS:
            errors.append(msg)
        elif len(errors) == MAX_ERRORS:
            errors.append(f"... further errors suppressed after {MAX_ERRORS} entries")

    required = {"name", "sku", "purchase_price", "sell_price"}
    for i, row in enumerate(reader, start=2):  # row 1 is header
        if i - 1 > MAX_ROWS:
            _record_error(f"Row {i}: import truncated — {MAX_ROWS} row limit reached")
            break
        missing = required - set(row.keys())
        if missing:
            _record_error(f"Row {i}: missing columns {missing}")
            continue
        try:
            name = (row["name"] or "").strip()
            sku = (row["sku"] or "").strip()
            # Enforce DB column caps early so the user gets row-level feedback
            # instead of a 500 from a DataError on commit.
            if not name or len(name) > 255:
                _record_error(f"Row {i}: name must be 1–255 characters")
                continue
            if not sku or len(sku) > 100:
                _record_error(f"Row {i}: sku must be 1–100 characters")
                continue
            # .limit(1): see the note in create_product. The Product table
            # has no UNIQUE(org_id, sku) constraint, so a row whose SKU
            # already appears on two or more existing products would make
            # this `db.scalar()` raise MultipleResultsFound and surface as
            # a generic "Row N: ..." import error instead of deterministic
            # upsert behaviour.
            existing = await db.scalar(
                select(Product)
                .where(Product.org_id == org_id, Product.sku == sku)
                .limit(1)
            )
            purchase_price = Decimal(row["purchase_price"])
            sell_price = Decimal(row["sell_price"])
            tax_rate = Decimal(row.get("tax_rate", "25.00") or "25.00")
            if purchase_price < 0 or sell_price < 0:
                _record_error(f"Row {i}: prices cannot be negative")
                continue
            # Upper bound matches the PositiveDecimal cap on API schemas so
            # numeric overflow cannot sneak in via CSV import.
            if purchase_price > Decimal("1000000") or sell_price > Decimal("1000000"):
                _record_error(f"Row {i}: prices must be ≤ 1 000 000")
                continue
            if tax_rate < 0 or tax_rate > 100:
                _record_error(f"Row {i}: tax_rate must be between 0 and 100")
                continue
            # Optional reorder_level — drives the daily low-stock email.
            # Skip the column entirely on rows that don't supply it so
            # existing CSVs keep working; fall back to 0 (the DB default).
            try:
                reorder_raw = (row.get("reorder_level") or "0").strip() or "0"
                reorder_level = int(reorder_raw)
            except ValueError:
                _record_error(f"Row {i}: reorder_level must be a whole number")
                continue
            if reorder_level < 0 or reorder_level > 1_000_000:
                _record_error(f"Row {i}: reorder_level must be between 0 and 1 000 000")
                continue
            data = {
                "name": name,
                "sku": sku,
                "category": (row.get("category") or "").strip() or None,
                "unit": (row.get("unit") or "st").strip() or "st",
                "purchase_price": purchase_price,
                "sell_price": sell_price,
                "tax_rate": tax_rate,
                "reorder_level": reorder_level,
            }
            if existing:
                for k, v in data.items():
                    setattr(existing, k, v)
                updated += 1
            else:
                db.add(Product(org_id=org_id, **data))
                created += 1
        except Exception as e:
            _record_error(f"Row {i}: {e}")

    await db.commit()
    return CSVImportResult(created=created, updated=updated, errors=errors)


@router.get("/products/{product_id}/forecast", response_model=DemandForecastOut)
async def get_demand_forecast(
    product_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    product = await db.scalar(
        select(Product).where(Product.id == product_id, Product.org_id == org_id)
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Average monthly OUT movements over last 3 months.
    #
    # Divide total OUT over the last 3 months by a fixed `3.0`, not
    # `AVG()` over grouped months — `GROUP BY DATE_TRUNC('month', …)`
    # only emits rows for months that had at least one movement, so a
    # product with 30 units sold in one month and nothing in the other
    # two was reported as "30/month" instead of "10/month". The
    # downstream `months_of_stock = current_stock / avg_usage` figure
    # was then 3× too low, triggering spurious low-stock alerts on
    # sporadically-sold SKUs.
    avg_result = await db.execute(
        text("""
            SELECT COALESCE(SUM(quantity), 0) / 3.0 AS avg_usage
            FROM stock_movements
            WHERE product_id = :pid
              AND org_id = :oid
              AND type = 'OUT'
              AND created_at >= NOW() - INTERVAL '3 months'
        """),
        {"pid": str(product_id), "oid": str(org_id)},
    )
    avg_usage = Decimal(str(avg_result.scalar_one() or 0))

    # Total current stock
    stock_result = await db.execute(
        select(func.coalesce(func.sum(StockLevel.quantity), 0)).where(
            StockLevel.product_id == product_id
        )
    )
    current_stock = stock_result.scalar_one()

    months_of_stock = (
        Decimal(str(current_stock)) / avg_usage if avg_usage > 0 else None
    )

    return DemandForecastOut(
        product_id=product_id,
        avg_monthly_usage=avg_usage,
        months_of_stock=months_of_stock,
        current_stock=current_stock,
    )


# ── Suppliers ─────────────────────────────────────────────────────────────────

@router.get("/suppliers", response_model=list[SupplierOut])
async def list_suppliers(
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Supplier)
        .where(Supplier.org_id == _org(ctx), Supplier.is_active == True)
        .order_by(Supplier.name)
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.post("/suppliers", response_model=SupplierOut, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    body: SupplierCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    supplier = Supplier(org_id=_org(ctx), **body.model_dump())
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    return supplier


@router.put("/suppliers/{supplier_id}", response_model=SupplierOut)
async def update_supplier(
    supplier_id: uuid.UUID,
    body: SupplierUpdate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    supplier = await db.scalar(
        select(Supplier).where(Supplier.id == supplier_id, Supplier.org_id == _org(ctx))
    )
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(supplier, k, v)
    await db.commit()
    await db.refresh(supplier)
    return supplier


# ── Warehouses ────────────────────────────────────────────────────────────────

@router.get("/warehouses", response_model=list[WarehouseOut])
async def list_warehouses(
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Warehouse)
        .where(Warehouse.org_id == _org(ctx), Warehouse.is_active == True)
        .order_by(Warehouse.name)
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.post("/warehouses", response_model=WarehouseOut, status_code=status.HTTP_201_CREATED)
async def create_warehouse(
    body: WarehouseCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    # ── Plan limit: max warehouses ─────────────────────────────────────────────
    _org_plan = await db.scalar(select(Organization.plan).where(Organization.id == org_id))
    _wh_count = await db.scalar(
        select(func.count()).select_from(Warehouse).where(Warehouse.org_id == org_id)
    ) or 0
    try:
        check_limit(_org_plan, RESOURCE_WAREHOUSES, _wh_count)
    except LimitExceededError as _exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "PLAN_LIMIT_EXCEEDED",
                "resource": RESOURCE_WAREHOUSES,
                "limit": _exc.limit,
                "current": _exc.current,
            },
        )
    # ──────────────────────────────────────────────────────────────────────────
    wh = Warehouse(org_id=org_id, **body.model_dump())
    db.add(wh)
    await db.commit()
    await db.refresh(wh)
    return wh


@router.put("/warehouses/{warehouse_id}", response_model=WarehouseOut)
async def update_warehouse(
    warehouse_id: uuid.UUID,
    body: WarehouseUpdate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    wh = await db.scalar(
        select(Warehouse).where(
            Warehouse.id == warehouse_id, Warehouse.org_id == _org(ctx)
        )
    )
    if not wh:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(wh, k, v)
    await db.commit()
    await db.refresh(wh)
    return wh


# ── Stock Levels ──────────────────────────────────────────────────────────────

@router.get("/stock", response_model=list[StockLevelOut])
async def list_stock(
    warehouse_id: Optional[uuid.UUID] = Query(None),
    low_stock_only: bool = Query(False),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(StockLevel)
        .options(
            selectinload(StockLevel.product),
            selectinload(StockLevel.warehouse),
        )
        .where(StockLevel.org_id == _org(ctx))
    )
    if warehouse_id:
        q = q.where(StockLevel.warehouse_id == warehouse_id)
    if low_stock_only:
        # StockLevel.min_threshold is a per-warehouse override; when 0 (the
        # default, which most rows carry since the threshold endpoint is
        # rarely used) we fall back to Product.reorder_level so the daily
        # reorder list actually surfaces low stock instead of always being
        # empty.
        effective_threshold = func.coalesce(
            func.nullif(StockLevel.min_threshold, 0),
            Product.reorder_level,
            0,
        )
        q = q.join(Product, Product.id == StockLevel.product_id).where(
            effective_threshold > 0,
            StockLevel.quantity < effective_threshold,
        )
    result = await db.execute(q.order_by(StockLevel.updated_at.desc()).limit(limit).offset(offset))
    levels = result.scalars().all()

    def _is_low(sl: StockLevel) -> bool:
        threshold = sl.min_threshold if sl.min_threshold and sl.min_threshold > 0 else int(sl.product.reorder_level or 0)
        return threshold > 0 and sl.quantity < threshold

    return [
        StockLevelOut(
            **{c: getattr(sl, c) for c in ["id", "product_id", "warehouse_id", "quantity", "min_threshold", "updated_at"]},
            is_low=_is_low(sl),
            product=sl.product,
            warehouse=sl.warehouse,
        )
        for sl in levels
    ]


@router.put("/stock/{product_id}/{warehouse_id}/threshold", response_model=StockLevelOut)
async def update_threshold(
    product_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    body: StockThresholdUpdate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    sl = await db.scalar(
        select(StockLevel)
        .options(selectinload(StockLevel.product), selectinload(StockLevel.warehouse))
        .where(
            StockLevel.product_id == product_id,
            StockLevel.warehouse_id == warehouse_id,
            StockLevel.org_id == _org(ctx),
        )
    )
    if not sl:
        raise HTTPException(status_code=404, detail="Stock level not found")
    sl.min_threshold = body.min_threshold
    await db.commit()
    await db.refresh(sl)
    effective = sl.min_threshold if sl.min_threshold and sl.min_threshold > 0 else int(sl.product.reorder_level or 0)
    return StockLevelOut(
        **{c: getattr(sl, c) for c in ["id", "product_id", "warehouse_id", "quantity", "min_threshold", "updated_at"]},
        is_low=effective > 0 and sl.quantity < effective,
        product=sl.product,
        warehouse=sl.warehouse,
    )


# ── Stock Movements ───────────────────────────────────────────────────────────

@router.get("/movements", response_model=list[StockMovementOut])
async def list_movements(
    product_id: Optional[uuid.UUID] = Query(None),
    warehouse_id: Optional[uuid.UUID] = Query(None),
    type: Optional[StockMovementType] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(StockMovement)
        .options(
            selectinload(StockMovement.product),
            selectinload(StockMovement.warehouse),
        )
        .where(StockMovement.org_id == _org(ctx))
    )
    if product_id:
        q = q.where(StockMovement.product_id == product_id)
    if warehouse_id:
        q = q.where(StockMovement.warehouse_id == warehouse_id)
    if type:
        q = q.where(StockMovement.type == type)
    result = await db.execute(
        q.order_by(StockMovement.created_at.desc()).offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.post("/movements", response_model=StockMovementOut, status_code=status.HTTP_201_CREATED)
async def create_movement(
    body: StockMovementCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)

    # Verify product + warehouse belong to org
    product = await db.scalar(
        select(Product).where(Product.id == body.product_id, Product.org_id == org_id)
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    warehouse = await db.scalar(
        select(Warehouse).where(
            Warehouse.id == body.warehouse_id, Warehouse.org_id == org_id
        )
    )
    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")

    # Upsert stock level — row-lock to serialise concurrent movements on the
    # same (product, warehouse) pair. Without FOR UPDATE two concurrent OUT
    # movements can both pass the sufficiency check and drive quantity negative.
    sl = await db.scalar(
        select(StockLevel).where(
            StockLevel.product_id == body.product_id,
            StockLevel.warehouse_id == body.warehouse_id,
        ).with_for_update()
    )
    if not sl:
        sl = StockLevel(
            org_id=org_id,
            product_id=body.product_id,
            warehouse_id=body.warehouse_id,
            quantity=0,
        )
        db.add(sl)
        await db.flush()

    if body.type == StockMovementType.IN:
        sl.quantity += body.quantity
    elif body.type == StockMovementType.OUT:
        if sl.quantity < body.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock: {sl.quantity} available",
            )
        sl.quantity -= body.quantity
    else:  # ADJUSTMENT
        sl.quantity = body.quantity

    movement = StockMovement(
        org_id=org_id,
        product_id=body.product_id,
        warehouse_id=body.warehouse_id,
        type=body.type,
        quantity=body.quantity,
        reference=body.reference,
        note=body.note,
    )
    db.add(movement)
    # Audit manual stock adjustments — automatic movements (POS sales, POs)
    # already carry a reference number; only manual ADJUSTMENT writes warrant
    # an explicit audit trail entry for compliance (BFL 5 kap. § lagervärde).
    if body.type == StockMovementType.ADJUSTMENT:
        _, member = ctx
        db.add(AuditLogEntry(
            org_id=org_id,
            actor_user_id=member.user_id,
            action="inventory.stock_adjustment",
            target_type="product",
            target_id=str(body.product_id),
            extra={
                "warehouse_id": str(body.warehouse_id),
                "new_quantity": body.quantity,
                "note": body.note,
            },
        ))
    await db.commit()

    # Reload with relationships
    result = await db.execute(
        select(StockMovement)
        .options(
            selectinload(StockMovement.product),
            selectinload(StockMovement.warehouse),
        )
        .where(StockMovement.id == movement.id)
    )
    return result.scalar_one()


# ── Purchase Orders ───────────────────────────────────────────────────────────

@router.get("/purchase-orders", response_model=list[PurchaseOrderOut])
async def list_purchase_orders(
    status: Optional[PurchaseOrderStatus] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.supplier),
            selectinload(PurchaseOrder.items),
        )
        .where(PurchaseOrder.org_id == _org(ctx))
    )
    if status:
        q = q.where(PurchaseOrder.status == status)
    result = await db.execute(q.order_by(PurchaseOrder.created_at.desc()).limit(limit).offset(offset))
    return result.scalars().all()


@router.post("/purchase-orders", response_model=PurchaseOrderOut, status_code=status.HTTP_201_CREATED)
async def create_purchase_order(
    body: PurchaseOrderCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)

    supplier = await db.scalar(
        select(Supplier).where(Supplier.id == body.supplier_id, Supplier.org_id == org_id)
    )
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    po = PurchaseOrder(
        org_id=org_id,
        supplier_id=body.supplier_id,
        status=PurchaseOrderStatus.DRAFT,
        notes=body.notes,
    )
    db.add(po)
    await db.flush()

    # Batch-validate every product in one IN (…) query instead of per-line
    # lookups (previously O(N) DB round-trips per PO). Also confirms every
    # line's product belongs to this org, blocking a spoofed product_id
    # from sneaking cross-tenant data onto a PO.
    requested_ids = {item.product_id for item in body.items}
    if requested_ids:
        valid_rows = (
            await db.scalars(
                select(Product.id).where(
                    Product.id.in_(requested_ids),
                    Product.org_id == org_id,
                )
            )
        ).all()
        valid_set = set(valid_rows)
        missing = requested_ids - valid_set
        if missing:
            raise HTTPException(
                status_code=404,
                detail=f"Product {next(iter(missing))} not found",
            )

    total = Decimal("0")
    for item_data in body.items:
        line_total = Decimal(str(item_data.unit_price)) * item_data.quantity
        total += line_total
        db.add(
            PurchaseOrderItem(
                purchase_order_id=po.id,
                product_id=item_data.product_id,
                quantity=item_data.quantity,
                unit_price=item_data.unit_price,
                line_total=line_total,
            )
        )
    po.total = total
    await db.commit()

    result = await db.execute(
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.supplier),
            selectinload(PurchaseOrder.items),
        )
        .where(PurchaseOrder.id == po.id)
    )
    return result.scalar_one()


@router.get("/purchase-orders/{po_id}", response_model=PurchaseOrderOut)
async def get_purchase_order(
    po_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.supplier),
            selectinload(PurchaseOrder.items),
        )
        .where(PurchaseOrder.id == po_id, PurchaseOrder.org_id == _org(ctx))
    )
    po = result.scalar_one_or_none()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return po


@router.patch("/purchase-orders/{po_id}/status", response_model=PurchaseOrderOut)
async def update_po_status(
    po_id: uuid.UUID,
    body: PurchaseOrderStatusUpdate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    # Lock the PO row so two concurrent PATCHes to RECEIVED cannot both
    # pass the `po.status == body.status` early-return and both post IN
    # movements, which would double the received quantity.
    result = await db.execute(
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.supplier),
            selectinload(PurchaseOrder.items),
        )
        .where(PurchaseOrder.id == po_id, PurchaseOrder.org_id == _org(ctx))
        .with_for_update(of=PurchaseOrder)
    )
    po = result.scalar_one_or_none()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    # Idempotency: transitioning to RECEIVED triggers stock increments. If the
    # PO is already RECEIVED, return the current state instead of incrementing
    # stock a second time.
    if po.status == body.status:
        return po

    # Disallow transitions away from RECEIVED — stock movements have already
    # been posted and reversing them by flipping the status is not safe.
    if po.status == PurchaseOrderStatus.RECEIVED and body.status != PurchaseOrderStatus.RECEIVED:
        raise HTTPException(
            status_code=422,
            detail="Cannot change status after a purchase order has been received.",
        )

    po.status = body.status

    # When marking as RECEIVED, auto-create IN movements for each line
    if body.status == PurchaseOrderStatus.RECEIVED:
        # Get default warehouse (first active one, deterministically — pick
        # the earliest-created so the same org always lands PO stock in
        # the same place across concurrent receives).
        wh = await db.scalar(
            select(Warehouse).where(
                Warehouse.org_id == _org(ctx), Warehouse.is_active == True  # noqa: E712
            ).order_by(Warehouse.created_at)
        )
        # Hard-fail if the org has no active warehouse. Otherwise the PO
        # transitions to RECEIVED (irreversibly — the guard above blocks
        # moving back) but no stock ever gets added, AND the audit trail
        # has no StockMovement rows. Users then cannot reconcile their
        # inventory with the PO they "received". Better to reject the
        # transition and let them create/activate a warehouse first.
        if not wh:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Cannot receive a purchase order: no active warehouse exists. "
                    "Create or activate a warehouse first."
                ),
            )
        # Batch-lock all StockLevels for this warehouse/PO in one query.
        # Order by product_id so concurrent transactions that touch
        # overlapping product sets acquire locks in the same sequence —
        # avoids a deadlock between two simultaneous PO receives.
        product_ids = sorted({item.product_id for item in po.items})
        existing_rows = (
            await db.scalars(
                select(StockLevel)
                .where(
                    StockLevel.warehouse_id == wh.id,
                    StockLevel.product_id.in_(product_ids),
                )
                .order_by(StockLevel.product_id)
                .with_for_update()
            )
        ).all()
        existing = {sl.product_id: sl for sl in existing_rows}
        for item in po.items:
            sl = existing.get(item.product_id)
            if not sl:
                sl = StockLevel(
                    org_id=_org(ctx),
                    product_id=item.product_id,
                    warehouse_id=wh.id,
                    quantity=0,
                )
                db.add(sl)
                await db.flush()
                existing[item.product_id] = sl
            sl.quantity += item.quantity
            db.add(
                StockMovement(
                    org_id=_org(ctx),
                    product_id=item.product_id,
                    warehouse_id=wh.id,
                    type=StockMovementType.IN,
                    quantity=item.quantity,
                    reference=f"PO-{str(po_id)[:8].upper()}",
                )
            )

    await db.commit()
    await db.refresh(po)
    return po


@router.get("/purchase-orders/{po_id}/pdf")
async def download_po_pdf(
    po_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.supplier),
            selectinload(PurchaseOrder.items),
        )
        .where(PurchaseOrder.id == po_id, PurchaseOrder.org_id == _org(ctx))
    )
    po = result.scalar_one_or_none()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    # Enrich items with product names
    items_data = []
    for item in po.items:
        product = await db.get(Product, item.product_id)
        # Defence-in-depth: never leak a product from another org even if
        # a stale/cross-org product_id somehow ended up on this PO's items.
        if product and product.org_id != _org(ctx):
            product = None
        items_data.append({
            "product_name": product.name if product else "Unknown",
            "sku": product.sku if product else "",
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "line_total": item.line_total,
        })

    org = await db.get(Organization, _org(ctx))
    pdf_bytes = generate_purchase_order_pdf({
        "id": po.id,
        "created_at": po.created_at,
        "status": po.status.value,
        "supplier": {
            "name": po.supplier.name,
            "email": po.supplier.email,
            "address": po.supplier.address,
        },
        "items": items_data,
        "total": po.total,
        "notes": po.notes,
        "org_name": org.name if org else "Varuflow",
    })

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="PO-{str(po_id)[:8].upper()}.pdf"'
        },
    )
