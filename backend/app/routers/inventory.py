"""Inventory module: products, warehouses, stock, movements, suppliers, POs."""
import csv
import io
import uuid
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.inventory import (
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

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


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


@router.post("/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(
    body: ProductCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    existing = await db.scalar(
        select(Product).where(Product.org_id == org_id, Product.sku == body.sku)
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
    product = await db.scalar(
        select(Product).where(Product.id == product_id, Product.org_id == _org(ctx))
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.put("/products/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: uuid.UUID,
    body: ProductUpdate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    product = await db.scalar(
        select(Product).where(Product.id == product_id, Product.org_id == _org(ctx))
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    for k, v in body.model_dump(exclude_unset=True).items():
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
    await db.commit()


@router.post("/products/import", response_model=CSVImportResult)
async def import_products_csv(
    file: UploadFile = File(...),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Bulk import products from a CSV file.

    Expected columns: name, sku, category, unit, purchase_price, sell_price, tax_rate
    """
    org_id = _org(ctx)
    content = await file.read()
    text_content = content.decode("utf-8-sig")  # handle BOM
    reader = csv.DictReader(io.StringIO(text_content))

    created = updated = 0
    errors: list[str] = []

    required = {"name", "sku", "purchase_price", "sell_price"}
    for i, row in enumerate(reader, start=2):  # row 1 is header
        missing = required - set(row.keys())
        if missing:
            errors.append(f"Row {i}: missing columns {missing}")
            continue
        try:
            sku = row["sku"].strip()
            existing = await db.scalar(
                select(Product).where(Product.org_id == org_id, Product.sku == sku)
            )
            data = {
                "name": row["name"].strip(),
                "sku": sku,
                "category": row.get("category", "").strip() or None,
                "unit": row.get("unit", "st").strip() or "st",
                "purchase_price": Decimal(row["purchase_price"]),
                "sell_price": Decimal(row["sell_price"]),
                "tax_rate": Decimal(row.get("tax_rate", "25.00") or "25.00"),
            }
            if existing:
                for k, v in data.items():
                    setattr(existing, k, v)
                updated += 1
            else:
                db.add(Product(org_id=org_id, **data))
                created += 1
        except Exception as e:
            errors.append(f"Row {i}: {e}")

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

    # Average monthly OUT movements over last 3 months
    avg_result = await db.execute(
        text("""
            SELECT COALESCE(AVG(monthly_total), 0) AS avg_usage
            FROM (
                SELECT DATE_TRUNC('month', created_at) AS m, SUM(quantity) AS monthly_total
                FROM stock_movements
                WHERE product_id = :pid
                  AND type = 'OUT'
                  AND created_at >= NOW() - INTERVAL '3 months'
                GROUP BY 1
            ) sub
        """),
        {"pid": str(product_id)},
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
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Supplier)
        .where(Supplier.org_id == _org(ctx), Supplier.is_active == True)
        .order_by(Supplier.name)
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
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Warehouse)
        .where(Warehouse.org_id == _org(ctx), Warehouse.is_active == True)
        .order_by(Warehouse.name)
    )
    return result.scalars().all()


@router.post("/warehouses", response_model=WarehouseOut, status_code=status.HTTP_201_CREATED)
async def create_warehouse(
    body: WarehouseCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    wh = Warehouse(org_id=_org(ctx), **body.model_dump())
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
        q = q.where(StockLevel.quantity < StockLevel.min_threshold)
    result = await db.execute(q.order_by(StockLevel.updated_at.desc()))
    levels = result.scalars().all()
    return [
        StockLevelOut(
            **{c: getattr(sl, c) for c in ["id", "product_id", "warehouse_id", "quantity", "min_threshold", "updated_at"]},
            is_low=sl.quantity < sl.min_threshold,
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
    return StockLevelOut(
        **{c: getattr(sl, c) for c in ["id", "product_id", "warehouse_id", "quantity", "min_threshold", "updated_at"]},
        is_low=sl.quantity < sl.min_threshold,
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

    # Upsert stock level
    sl = await db.scalar(
        select(StockLevel).where(
            StockLevel.product_id == body.product_id,
            StockLevel.warehouse_id == body.warehouse_id,
        )
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
    result = await db.execute(q.order_by(PurchaseOrder.created_at.desc()))
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

    total = Decimal("0")
    for item_data in body.items:
        product = await db.scalar(
            select(Product).where(
                Product.id == item_data.product_id, Product.org_id == org_id
            )
        )
        if not product:
            raise HTTPException(
                status_code=404, detail=f"Product {item_data.product_id} not found"
            )
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
    po.status = body.status

    # When marking as RECEIVED, auto-create IN movements for each line
    if body.status == PurchaseOrderStatus.RECEIVED:
        # Get default warehouse (first active one)
        wh = await db.scalar(
            select(Warehouse).where(
                Warehouse.org_id == _org(ctx), Warehouse.is_active == True
            )
        )
        if wh:
            for item in po.items:
                sl = await db.scalar(
                    select(StockLevel).where(
                        StockLevel.product_id == item.product_id,
                        StockLevel.warehouse_id == wh.id,
                    )
                )
                if not sl:
                    sl = StockLevel(
                        org_id=_org(ctx),
                        product_id=item.product_id,
                        warehouse_id=wh.id,
                        quantity=0,
                    )
                    db.add(sl)
                    await db.flush()
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
        items_data.append({
            "product_name": product.name if product else "Unknown",
            "sku": product.sku if product else "",
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "line_total": item.line_total,
        })

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
        "org_name": "Varuflow",  # TODO: use real org name from member context
    })

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="PO-{str(po_id)[:8].upper()}.pdf"'
        },
    )
