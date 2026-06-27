"""Pydantic schemas for the Inventory module."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field

from app.models.inventory import (
    PurchaseOrderStatus,
    StockMovementType,
)


# ── Shared ────────────────────────────────────────────────────────────────────

PositiveDecimal = Annotated[Decimal, Field(gt=0, le=Decimal("1000000"))]
NonNegativeInt = Annotated[int, Field(ge=0)]


# ── Product ───────────────────────────────────────────────────────────────────

class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    sku: str = Field(..., min_length=1, max_length=100)
    category: str | None = Field(None, max_length=100)
    unit: str = Field("st", max_length=50)
    purchase_price: PositiveDecimal
    sell_price: PositiveDecimal
    tax_rate: Decimal = Field(Decimal("25.00"), ge=0, le=100)
    description: str | None = Field(None, max_length=2000)
    # The daily low-stock email and the weekly digest filter on
    # `reorder_level > 0`. Until this field was exposed on the API,
    # every tenant's products sat at the 0 default and no alerts
    # ever fired — the whole low-stock pathway was dormant.
    reorder_level: int = Field(0, ge=0, le=1_000_000)


class ProductUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    sku: str | None = Field(None, min_length=1, max_length=100)
    category: str | None = Field(None, max_length=100)
    unit: str | None = Field(None, max_length=50)
    purchase_price: PositiveDecimal | None = None
    sell_price: PositiveDecimal | None = None
    tax_rate: Decimal | None = Field(None, ge=0, le=100)
    description: str | None = Field(None, max_length=2000)
    reorder_level: int | None = Field(None, ge=0, le=1_000_000)
    is_active: bool | None = None
    # v38 (Item 16) — per-product auto-reorder overrides. All optional so
    # existing integrations that PUT /products/{id} with the old body
    # shape keep working.
    auto_reorder_enabled: bool | None = None
    preferred_supplier_id: uuid.UUID | None = None
    reorder_quantity: int | None = Field(None, ge=0, le=1_000_000)
    reorder_lead_buffer_days: int | None = Field(None, ge=0, le=365)


class ProductOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    sku: str
    category: str | None
    unit: str
    purchase_price: Decimal
    sell_price: Decimal
    tax_rate: Decimal
    description: str | None
    reorder_level: int
    is_active: bool
    # v38 (Item 16) — surface auto-reorder fields on the list / detail
    # endpoints so the inventory UI can render the badge and the
    # per-product settings form without a second round-trip.
    auto_reorder_enabled: bool = True
    preferred_supplier_id: uuid.UUID | None = None
    reorder_quantity: int | None = None
    reorder_lead_buffer_days: int = 3
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Supplier ──────────────────────────────────────────────────────────────────

class SupplierCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    address: str | None = Field(None, max_length=500)
    country: str = Field("Sweden", max_length=100)
    # v41 (Item 20) — opt-in: when True, the PO receive endpoint also
    # creates a DRAFT payable invoice for this supplier. Default off so
    # supplier creation behaviour is unchanged.
    create_invoice_on_receipt: bool = False


class SupplierUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    address: str | None = Field(None, max_length=500)
    country: str | None = Field(None, max_length=100)
    is_active: bool | None = None
    create_invoice_on_receipt: bool | None = None


class SupplierOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    email: str | None
    phone: str | None
    address: str | None
    country: str
    is_active: bool
    create_invoice_on_receipt: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Warehouse ─────────────────────────────────────────────────────────────────

class WarehouseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    location: str | None = Field(None, max_length=500)


class WarehouseUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    location: str | None = None
    is_active: bool | None = None


class WarehouseOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    location: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Stock Level ───────────────────────────────────────────────────────────────

class StockLevelOut(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    warehouse_id: uuid.UUID
    quantity: int
    min_threshold: int
    updated_at: datetime
    is_low: bool  # computed: quantity < min_threshold
    product: ProductOut
    warehouse: WarehouseOut

    model_config = {"from_attributes": True}


class StockThresholdUpdate(BaseModel):
    min_threshold: NonNegativeInt


# ── Stock Movement ────────────────────────────────────────────────────────────

class StockMovementCreate(BaseModel):
    product_id: uuid.UUID
    warehouse_id: uuid.UUID
    type: StockMovementType
    # DB column is PG Integer (int32 — max 2_147_483_647). Cap well below
    # the limit so cumulative in-session totals still fit; no legitimate
    # Nordic wholesaler moves 100M units in a single transaction.
    quantity: int = Field(..., gt=0, le=100_000_000)
    reference: str | None = Field(None, max_length=255)
    note: str | None = Field(None, max_length=2000)
    # v28 — explicit batch selection. When the product has batches and
    # the movement is OUT, the router auto-picks FEFO if ``batch_id``
    # is None. Set to an explicit UUID to override (e.g. FIFO, recall).
    batch_id: uuid.UUID | None = None


class StockMovementOut(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    warehouse_id: uuid.UUID
    type: StockMovementType
    quantity: int
    reference: str | None
    note: str | None
    batch_id: uuid.UUID | None = None
    created_at: datetime
    product: ProductOut
    warehouse: WarehouseOut

    model_config = {"from_attributes": True}


# ── Purchase Order ────────────────────────────────────────────────────────────

class PurchaseOrderItemCreate(BaseModel):
    product_id: uuid.UUID
    # PG column is Integer (int32), but the real constraint is that
    # `quantity * unit_price` must fit PurchaseOrderItem.line_total
    # Numeric(14,2) — max ≈ 10^12. With unit_price capped at 10^6 via
    # PositiveDecimal, quantity must stay ≤ 10^6 so line_total ≤ 10^12.
    # Matches InvoiceLineItemCreate.quantity.
    quantity: int = Field(..., gt=0, le=1_000_000)
    unit_price: PositiveDecimal


class PurchaseOrderCreate(BaseModel):
    supplier_id: uuid.UUID
    notes: str | None = Field(None, max_length=2000)
    # Cap the number of line items per PO. A 1000-line PO is already
    # pathological; without a limit a caller could submit 100k lines and
    # blow up both the batch product-validate query and the PDF render.
    items: list[PurchaseOrderItemCreate] = Field(..., min_length=1, max_length=500)


class PurchaseOrderItemOut(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    quantity: int
    unit_price: Decimal
    line_total: Decimal

    model_config = {"from_attributes": True}


class PurchaseOrderOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    supplier_id: uuid.UUID
    status: PurchaseOrderStatus
    total: Decimal
    notes: str | None
    created_at: datetime
    supplier: SupplierOut
    items: list[PurchaseOrderItemOut]

    model_config = {"from_attributes": True}


class PurchaseOrderStatusUpdate(BaseModel):
    status: PurchaseOrderStatus


# ── Forecast ──────────────────────────────────────────────────────────────────

class DemandForecastOut(BaseModel):
    product_id: uuid.UUID
    avg_monthly_usage: Decimal
    months_of_stock: Decimal | None  # None if no stock data
    current_stock: int


# ── CSV Import ────────────────────────────────────────────────────────────────

class CSVImportResult(BaseModel):
    created: int
    updated: int
    errors: list[str]
    # Item 19 — AI auto-categorisation summary. All optional so older
    # clients still deserialise without the extra fields.
    auto_categorized: int = 0
    needs_review: int = 0
    ai_skipped: bool = False
    ai_reason: str | None = None


# ── Pagination ────────────────────────────────────────────────────────────────

class PaginatedProducts(BaseModel):
    items: list[ProductOut]
    total: int
    skip: int
    limit: int


# ── Batches (v28) ─────────────────────────────────────────────────────────────

class ProductBatchCreate(BaseModel):
    product_id: uuid.UUID
    warehouse_id: uuid.UUID
    batch_number: str = Field(..., min_length=1, max_length=100)
    expiry_date: date | None = None
    quantity: int = Field(..., gt=0, le=100_000_000)
    # PO receipt reference so the IN movement can be attributed to the
    # purchase order that triggered the batch registration.
    reference: str | None = Field(None, max_length=255)


class ProductBatchOut(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    warehouse_id: uuid.UUID
    batch_number: str
    expiry_date: date | None
    quantity: int
    created_at: datetime

    model_config = {"from_attributes": True}



# ── Payable invoices (Item 20) ────────────────────────────────────────────────

class PayableInvoiceOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    supplier_id: uuid.UUID
    purchase_order_id: uuid.UUID | None
    status: str
    invoice_number: str | None
    issue_date: date | None
    due_date: date | None
    subtotal: Decimal
    tax_amount: Decimal
    total: Decimal
    currency: str
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
