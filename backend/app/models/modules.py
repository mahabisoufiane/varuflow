"""Module permission system — controls which app modules each team member can access.

Tables:
- ``modules``: Registry of available app modules (seeded, ~10 rows)
- ``member_modules``: Per-user module grants assigned by OWNER/ADMIN
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Module(Base):
    """Registry of available application modules.

    Seeded via migration or startup script. Each row maps a module key
    to the frontend routes and backend API prefixes it covers, plus the
    minimum plan tier required to unlock it.
    """
    __tablename__ = "modules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    routes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    api_prefixes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    min_plan: Mapped[str] = mapped_column(String(20), default="FREE", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class MemberModule(Base):
    """Per-user module grant — exists only for members with restricted access.

    OWNER and ADMIN roles bypass this table entirely (they have access to all
    modules their plan allows). Only MEMBER-role users with
    ``module_access_mode = 'RESTRICTED'`` are checked against this table.
    """
    __tablename__ = "member_modules"
    __table_args__ = (
        UniqueConstraint("member_id", "module_key", name="uq_member_modules_member_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organization_members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    module_key: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("modules.key", ondelete="CASCADE"),
        nullable=False,
    )
    granted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
