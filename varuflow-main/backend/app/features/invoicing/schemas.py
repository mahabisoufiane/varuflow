"""Pydantic schemas for the Invoicing module."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from app.schemas.base import StrictModel
from .models import InvoiceStatus, PaymentMethod

PositiveDecimal = Annotated[Decimal, Field(gt=0, le=Decimal("1000000"))]


# ── Customer ──────────────────────────────────────────────────────────────────

class CustomerCreate(StrictModel):
    company_name: str = Field(..., min_length=1, max_length=255)
    org_number: str | None = Field(None, max_length=20)
    vat_number: str | None = Field(None, max_length=30)
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    address: str | None = Field(None, max_length=500)
    payment_terms_days: int = Field(30, ge=0, le=365)

    @field_validator("email")
    @classmethod
    def _validate_email(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().lower()
        if not v:
            return None
        # Lightweight RFC-ish check — enough to reject "hello" or "a@b"
        # before we try to email this customer and Resend rejects the
        # message, or worse, we send to an unintended inbox.
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email address")
        return v


class CustomerUpdate(StrictModel):
    # Partial-update semantics — every field is optional so a PUT that
    # only wants to rename the customer does not need to resubmit every
    # existing value. The router applies `model_dump(exclude_unset=True)`
    # so unspecified fields are left untouched. If CustomerUpdate
    # inherited CustomerCreate instead (where company_name is required
    # via `Field(..., min_length=1)`), Pydantic would 422 any PATCH-style
    # update that omits company_name — well before the router's
    # exclude_unset logic runs — breaking the advertised partial-update
    # UX on every path except "change the company name".
    company_name: str | None = Field(None, min_length=1, max_length=255)
    org_number: str | None = Field(None, max_length=20)
    vat_number: str | None = Field(None, max_length=30)
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    address: str | None = Field(None, max_length=500)
    payment_terms_days: int | None = Field(None, ge=0, le=365)
    # Reactivate an archived customer (DELETE /customers/{id} flips
    # is_active=False — the only way back is to PUT is_active=true).
    # Without this field there was no supported path to un-archive,
    # which was a one-way trap now that create_invoice and
    # recurring.run_now refuse to bill archived customers. Optional so
    # exclude_unset keeps it a no-op on updates that don't touch it.
    is_active: bool | None = Field(None)

    # Reuse the same email normalizer as CustomerCreate so PUT also
    # lowercases/strips and rejects obviously-malformed addresses.
    # `@field_validator` must be registered at class-creation time on
    # *this* class — a simple attribute reassignment from the parent
    # would not hook into Pydantic's validator registry.
    @field_validator("email")
    @classmethod
    def _validate_email(cls, v: str | None) -> str | None:
        return CustomerCreate._validate_email(v)


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

class InvoiceLineItemCreate(StrictModel):
    product_id: uuid.UUID | None = None
    description: str = Field(..., min_length=1, max_length=500)
    # Caps match the underlying Postgres columns (quantity Numeric(10,3),
    # unit_price Numeric(12,2)) minus headroom so that quantity * unit_price
    # still fits in line_total's Numeric(14,2) (max ~1e12). Without these
    # caps, oversized submissions cause a "numeric field overflow" 500.
    quantity: Decimal = Field(..., gt=0, le=Decimal("1000000"), decimal_places=3)
    unit_price: Decimal = Field(..., ge=0, le=Decimal("1000000"), decimal_places=2)
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

class InvoiceCreate(StrictModel):
    customer_id: uuid.UUID
    issue_date: date
    due_date: date
    notes: str | None = Field(None, max_length=2000)
    # Cap line items so a single POST cannot blow up memory / PDF render time.
    items: list[InvoiceLineItemCreate] = Field(..., min_length=1, max_length=500)
    invoice_type: str = Field("standard", pattern="^(standard|deposit|final)$")
    deposit_amount: Decimal | None = Field(None, ge=0)
    parent_invoice_id: uuid.UUID | None = None

    @field_validator("issue_date")
    @classmethod
    def _issue_not_future(cls, v: date):
        # Swedish bokföringslagen (BFL) 5 kap. 6 § requires an invoice's
        # issue date to reflect the actual supply / service delivery —
        # it cannot be a future date. VAT reporting uses issue_date to
        # bucket the sale into the right period, so a future-dated
        # invoice either lands in a period that hasn't happened yet
        # (under-reporting the current period) or breaks the
        # chronological ordering audits require. Pydantic otherwise
        # only enforces the type, so without this guard a dashboard
        # typo ("2099-04-22") silently creates a future-dated invoice
        # that shows up nowhere until that year arrives. Matches the
        # symmetric `payment_date > today` guard already in
        # record_payment.
        if v > date.today():
            raise ValueError("issue_date cannot be in the future")
        return v

    @field_validator("due_date")
    @classmethod
    def _due_after_issue(cls, v: date, info):
        issue = info.data.get("issue_date")
        if issue is not None and v < issue:
            raise ValueError("due_date cannot be earlier than issue_date")
        return v


class InvoiceStatusUpdate(StrictModel):
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
    stripe_payment_link_url: str | None = None
    stripe_payment_link_status: str | None = None
    created_at: datetime
    line_items: list[InvoiceLineItemOut]
    invoice_type: str = "standard"
    deposit_amount: Decimal | None = None
    parent_invoice_id: uuid.UUID | None = None

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

class PaymentCreate(StrictModel):
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
