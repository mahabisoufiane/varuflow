"""Pydantic schemas for the Invoicing module."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field

from app.models.invoicing import InvoiceStatus, PaymentMethod, RecurringFrequency

PositiveDecimal = Annotated[Decimal, Field(gt=0)]


# ── Customer ──────────────────────────────────────────────────────────────────

class CustomerCreate(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255)
    org_number: str | None = Field(None, max_length=20)
    vat_number: str | None = Field(None, max_length=30)
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    address: str | None = Field(None, max_length=500)
    payment_terms_days: int = Field(30, ge=0, le=365)


class CustomerUpdate(CustomerCreate):
    pass


class CustomerOut(BaseModel):
    id: uuid.UUID
    company_name: str
    org_number: str | None
    vat_number: str | None
    email: str | None
    phone: str | None
    address: str | None
    payment_terms_days: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Invoice line items ────────────────────────────────────────────────────────

class InvoiceLineItemCreate(BaseModel):
    product_id: uuid.UUID | None = None
    description: str = Field(..., min_length=1, max_length=500)
    quantity: Decimal = Field(..., gt=0, decimal_places=3)
    unit_price: Decimal = Field(..., ge=0, decimal_places=2)
    tax_rate: Decimal = Field(Decimal("25.00"), ge=0, le=100)


class InvoiceLineItemOut(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID | None
    description: str
    quantity: Decimal
    unit_price: Decimal
    tax_rate: Decimal
    line_total: Decimal

    model_config = {"from_attributes": True}


# ── Invoice ───────────────────────────────────────────────────────────────────

class InvoiceCreate(BaseModel):
    customer_id: uuid.UUID
    issue_date: date
    due_date: date
    notes: str | None = None
    items: list[InvoiceLineItemCreate] = Field(..., min_length=1)


class InvoiceStatusUpdate(BaseModel):
    status: InvoiceStatus


class InvoiceOut(BaseModel):
    id: uuid.UUID
    invoice_number: str
    customer_id: uuid.UUID
    customer: CustomerOut
    issue_date: date
    due_date: date
    status: InvoiceStatus
    subtotal: Decimal
    vat_amount: Decimal
    total_sek: Decimal
    notes: str | None
    created_at: datetime
    line_items: list[InvoiceLineItemOut]

    model_config = {"from_attributes": True}


class InvoiceSummary(BaseModel):
    id: uuid.UUID
    invoice_number: str
    customer: CustomerOut
    issue_date: date
    due_date: date
    status: InvoiceStatus
    total_sek: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Payment ───────────────────────────────────────────────────────────────────

class PaymentCreate(BaseModel):
    amount: PositiveDecimal
    payment_date: date
    method: PaymentMethod = PaymentMethod.BANK_TRANSFER
    reference: str | None = Field(None, max_length=255)


class PaymentOut(BaseModel):
    id: uuid.UUID
    invoice_id: uuid.UUID
    amount: Decimal
    payment_date: date
    method: PaymentMethod
    reference: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Aging report ──────────────────────────────────────────────────────────────

class AgingBucket(BaseModel):
    customer: str
    invoice_number: str
    invoice_id: uuid.UUID
    total_sek: Decimal
    due_date: date
    days_overdue: int


class AgingReport(BaseModel):
    current: list[AgingBucket]       # not yet due
    days_1_30: list[AgingBucket]
    days_31_60: list[AgingBucket]
    days_61_90: list[AgingBucket]
    days_90_plus: list[AgingBucket]
    total_outstanding: Decimal
