import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OrgPlan(str, enum.Enum):
    FREE = "FREE"
    PRO = "PRO"


class OrgRole(str, enum.Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    org_number: Mapped[str | None] = mapped_column(String(20))  # Swedish org number
    vat_number: Mapped[str | None] = mapped_column(String(30))
    address: Mapped[str | None] = mapped_column(String(500))
    plan: Mapped[OrgPlan] = mapped_column(
        Enum(OrgPlan, name="org_plan"), default=OrgPlan.FREE, nullable=False
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String(100))
    fortnox_access_token: Mapped[str | None] = mapped_column(String(2000))
    fortnox_refresh_token: Mapped[str | None] = mapped_column(String(2000))
    fortnox_token_expiry: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    members: Mapped[list["OrganizationMember"]] = relationship(
        "OrganizationMember", back_populates="organization"
    )


class OrganizationMember(Base):
    __tablename__ = "organization_members"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    # References auth.users in Supabase; plain UUID in local dev
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    role: Mapped[OrgRole] = mapped_column(
        Enum(OrgRole, name="org_role"), default=OrgRole.MEMBER, nullable=False
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="members"
    )


class FortnoxOAuthState(Base):
    """One-time CSRF nonce for Fortnox OAuth2 state parameter.

    Created on /fortnox/connect, consumed and deleted on /fortnox/callback.
    Expires after 10 minutes to prevent replay of stale links.
    """
    __tablename__ = "fortnox_oauth_states"

    id:         Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nonce:      Mapped[str]        = mapped_column(String(64), nullable=False, unique=True, index=True)
    org_id:     Mapped[uuid.UUID]  = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime]   = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime]   = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
