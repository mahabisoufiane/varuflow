"""MultiEntityRole — per-entity role override for group users."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MultiEntityRole(Base):
    """Allows a user to have a different role in a subsidiary org.

    When a user belongs to a group, their ``OrganizationMember`` row in HQ sets
    their default role. ``MultiEntityRole`` overrides that role for a specific
    subsidiary org — e.g. ADMIN in HQ, VIEWER in branch.
    """

    __tablename__ = "multi_entity_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "org_id", name="uq_multi_entity_roles_user_org"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    granted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
