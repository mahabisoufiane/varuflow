"""Kit / Assembly models: definitions, components, and assembly logs."""
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class KitDefinition(Base):
    __tablename__ = "kit_definitions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    # The "finished" kit product SKU (must already exist in products)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # If null → price = sum of component retail prices
    custom_price: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    components: Mapped[List["KitComponent"]] = relationship("KitComponent", back_populates="kit", cascade="all, delete-orphan")
    assemblies: Mapped[List["KitAssembly"]] = relationship("KitAssembly", back_populates="kit")


class KitComponent(Base):
    __tablename__ = "kit_components"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("kit_definitions.id", ondelete="CASCADE"), nullable=False, index=True)
    component_product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)

    kit: Mapped["KitDefinition"] = relationship("KitDefinition", back_populates="components")


class KitAssembly(Base):
    """Records a physical assemble or disassemble action."""
    __tablename__ = "kit_assemblies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    kit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("kit_definitions.id", ondelete="RESTRICT"), nullable=False, index=True)
    # positive = assemble (deduct components, add kit stock)
    # negative = disassemble (restore components, reduce kit stock)
    direction: Mapped[str] = mapped_column(String(12), nullable=False)  # "assemble" | "disassemble"
    quantity: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assembled_by_staff_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    assembled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    kit: Mapped["KitDefinition"] = relationship("KitDefinition", back_populates="assemblies")
