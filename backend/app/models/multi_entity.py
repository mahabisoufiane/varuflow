import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Any
from sqlalchemy import String, Text, Date, DateTime, Integer, Numeric, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class IntercompanyTransfer(Base):
    """Inter-entity stock, cash, or service transfer with arm's-length transfer pricing."""
    __tablename__ = "intercompany_transfers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    to_org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    transfer_type: Mapped[str] = mapped_column(String(20), nullable=False)          # stock|cash|service
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 4), nullable=True)
    transfer_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="SEK")
    description: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    elimination_entry_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    transfer_date: Mapped[date] = mapped_column(Date(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class EliminationEntry(Base):
    """Intercompany elimination entry for consolidated group reporting."""
    __tablename__ = "elimination_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(7), nullable=False)          # YYYY-MM
    entry_type: Mapped[str] = mapped_column(String(30), nullable=False)     # intercompany_revenue|intercompany_cogs|...
    from_org_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    to_org_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="SEK")
    description: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FranchiseAgreement(Base):
    """Franchise legal agreement between a franchisor org and a franchisee org."""
    __tablename__ = "franchise_agreements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    franchisor_org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    franchisee_org_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    franchisee_name: Mapped[str] = mapped_column(String(200), nullable=False)
    franchisee_email: Mapped[str] = mapped_column(String(200), nullable=False)
    franchisee_country: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    royalty_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, default=Decimal("0.05"))
    royalty_basis: Mapped[str] = mapped_column(String(20), nullable=False, default="gross_revenue")
    fixed_royalty_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="SEK")
    billing_cycle: Mapped[str] = mapped_column(String(10), nullable=False, default="monthly")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    start_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    metadata_: Mapped[Optional[Any]] = mapped_column("metadata", JSONB(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class RoyaltyBilling(Base):
    """Periodic royalty billing record for a franchise agreement."""
    __tablename__ = "royalty_billings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agreement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("franchise_agreements.id", ondelete="CASCADE"), nullable=False, index=True)
    franchisor_org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    franchisee_org_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    period: Mapped[str] = mapped_column(String(7), nullable=False)          # YYYY-MM
    revenue_basis: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 2), nullable=True)
    royalty_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="SEK")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    invoice_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FranchiseCatalogPush(Base):
    """Log of product catalogue pushes from franchisor to franchisee orgs."""
    __tablename__ = "franchise_catalog_pushes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    franchisor_org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    franchisee_org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    product_ids: Mapped[Any] = mapped_column(JSONB(), nullable=False)
    pushed_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    created_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    updated_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed")
    error_detail: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
