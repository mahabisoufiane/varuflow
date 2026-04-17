"""Pydantic schemas for the Inventory module."""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field

from app.models.inventory import (
    PurchaseOrderStatus,
    StockMovementType,
)


# ── Shared ────────────────────────────────────────────────────────────────────

PositiveDecimal = Annotated[Decimal, Field(gt=0)]
NonNegativeInt = Annotated[int, Field(ge=0)]


# ── Product ───────────────────────────────────────────────────────────────────

class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    sku: str = Field(..., min_length=1, max_length=100)
    barcode: str | None = Field(None, max_length=50)
    category: str | None = Field(None, max_length=100)
    unit: str = Field("st", max_length=50)
    purchase_price: PositiveDecimal
    sell_price: PositiveDecimal
    tax_rate: Decimal = Field(Decimal("25.00"), ge=0, le=100)
    reorder_level: int = Field(0, ge=0)
    description: str | None = None


class ProductUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    sku: str | None = Field(None, min_length=1, max_length=100)
    barcode: str | None = Field(None, max_length=50)
    category: str | None = None
    unit: str | None = Field(None, max_length=50)
    purchase_price: PositiveDecimal | None = None
    sell_price: PositiveDecimal | None = None
    tax_rate: Decimal | None = Field(None, ge=0, le=100)
    reorder_level: int | None = Field(None, ge=0)
    description: str | None = None
    is_active: bool | None = None


class ProductOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    sku: str
    barcode: str | None = None
    category: str | None
    unit: str
    purchase_price: Decimal
    sell_price: Decimal
    tax_rate: Decimal
    reorder_level: int = 0
    description: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Supplier ──────────────────────────────────────────────────────────────────

class SupplierCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    address: str | None = Field(None, max_length=500)
    country: str = Field("Sweden", max_length=100)


class SupplierUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    country: str | None = None
    is_active: bool | None = None


class SupplierOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    email: str | None
    phone: str | None
    address: str | None
    country: str
    is_active: bool
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
    quantity: int = Field(..., gt=0)
    reference: str | None = Field(None, max_length=255)
    note: str | None = None


class StockMovementOut(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    warehouse_id: uuid.UUID
    type: StockMovementType
    quantity: int
    reference: str | None
    note: str | None
    created_at: datetime
    product: ProductOut
    warehouse: WarehouseOut

    model_config = {"from_attributes": True}


# ── Purchase Order ────────────────────────────────────────────────────────────

class PurchaseOrderItemCreate(BaseModel):
    product_id: uuid.UUID
    quantity: int = Field(..., gt=0)
    unit_price: PositiveDecimal


class PurchaseOrderCreate(BaseModel):
    supplier_id: uuid.UUID
    notes: str | None = None
    items: list[PurchaseOrderItemCreate] = Field(..., min_length=1)


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


# ── Pagination ────────────────────────────────────────────────────────────────

class PaginatedProducts(BaseModel):
    items: list[ProductOut]
    total: int
    skip: int
    limit: int
