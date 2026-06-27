from __future__ import annotations

from typing import Optional

import enum
import uuid
from datetime import datetime, time

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Time, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, SoftDeleteMixin


class OrgPlan(str, enum.Enum):
    FREE = "FREE"
    PRO = "PRO"
    # v30 — added for Enterprise-only features (outbound webhooks, etc.).
    # Migration ALTER TYPEs the matching Postgres enum value.
    ENTERPRISE = "ENTERPRISE"


class OrgRole(str, enum.Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


class Organization(SoftDeleteMixin, Base):
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
    # v22 — destination for the "new portal order" internal email.
    # NULL disables the internal notification; the ordering customer
    # still receives their own confirmation.
    orders_notification_email: Mapped[str | None] = mapped_column(String(255))
    # v50 (Item 34) — base / reporting currency. All analytics totals
    # are normalised to this code; invoices / POS sales that omit an
    # explicit currency default to this value at creation time.
    base_currency: Mapped[str] = mapped_column(String(3), default="SEK", nullable=False)
    # v38 (Item 16) — Auto-reorder configuration. Disabled by default so
    # new tenants never have draft POs silently appearing in their
    # inventory on the morning after signup. Owners opt in from
    # Settings → Auto-reorder and can customise schedule & notify email.
    auto_reorder_enabled: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False, nullable=False
    )
    auto_reorder_time: Mapped[time] = mapped_column(
        Time, server_default="06:00:00", default=time(6, 0), nullable=False
    )
    # Comma-separated day-of-week codes (MON..SUN). The scheduler job
    # runs every day at auto_reorder_time but checks this field per
    # org and skips if today's code is not included.
    auto_reorder_days: Mapped[str] = mapped_column(
        String(64), server_default="MON,WED,FRI", default="MON,WED,FRI", nullable=False
    )
    # NULL → fall back to the owner's email (matches the existing
    # `_org_notification_email` helper used by the low-stock job).
    auto_reorder_notify_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # v42 (Item 21) — Nightly business summary email. Opt-in per org so
    # the v41 → v42 upgrade is behaviour-preserving. Delivery time is
    # stored as local time (Europe/Stockholm); the scheduler runs a
    # 15-minute sweep and each org fires in the window containing its
    # configured time.
    nightly_summary_enabled: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False, nullable=False
    )
    nightly_summary_time: Mapped[time] = mapped_column(
        Time, server_default="07:30:00", default=time(7, 30), nullable=False
    )
    # v47 (Item 31) — MENA Salon/Spa booking flags. All default-off so
    # non-salon tenants see no behaviour change. ``female_only_mode``
    # filters both staff and customer-visible booking UI to women only;
    # ``prayer_time_blocking_enabled`` + ``prayer_times`` (JSONB array)
    # carves prayer windows out of the slot-availability calculation.
    booking_female_only_mode: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False, nullable=False
    )
    booking_prayer_time_blocking_enabled: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False, nullable=False
    )
    # [{"name": "Dhuhr", "start": "12:15", "duration_minutes": 20}, ...]
    # Evaluated in the org's local timezone. NULL = no prayer windows
    # configured, so blocking — even when enabled — is a no-op.
    booking_prayer_times: Mapped[list | None] = mapped_column(
        JSONB, nullable=True
    )
    # v61 (Item 50) — Subscription pause tracking. ``is_paused`` is the
    # hot flag the write-guard middleware reads on every mutating
    # request; it's intentionally a plain boolean (not derived from
    # the open SubscriptionPause row) so the guard stays a single-
    # column read. The timestamps are for UI + the scheduler's
    # auto-resume / 7-day reminder jobs.
    is_paused: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False, nullable=False
    )
    paused_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    pause_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    pause_reminder_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Required to call ``stripe.Subscription.modify(pause_collection=...)``.
    # Filled in by the checkout webhook now that we need more than
    # the customer id.
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    # aa1bb2cc3dd4 — onboarding wizard + sandbox + fiscal year
    # The month (1–12) that the organisation's fiscal year begins.
    # Swedish companies default to 1 (calendar year); some use 4, 7, or 10.
    fiscal_year_start: Mapped[int] = mapped_column(
        Integer, server_default="1", default=1, nullable=False
    )
    # True when this is the pre-populated demo/sandbox organisation.
    # Sandbox orgs are owned by the same user but isolated from production.
    is_sandbox: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False, nullable=False
    )
    # Set to True once the first-run wizard is finished (prevents it from
    # re-appearing on next login).
    onboarding_wizard_completed: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False, nullable=False
    )
    # ── 14-day PRO trial ─────────────────────────────────────────────────────
    trial_plan: Mapped[str | None] = mapped_column(String(20), nullable=True)
    trial_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trial_converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trial_extended_count: Mapped[int] = mapped_column(Integer, server_default="0", default=0, nullable=False)
    trial_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # ─────────────────────────────────────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # v109 — Country workspaces. `entity_type` distinguishes standalone orgs
    # from parent hubs and country branches. `parent_org_id` links a branch
    # back to its hub. `country_code` is ISO-3166-1 alpha-2 (SE, NO, DK…).
    entity_type: Mapped[str] = mapped_column(
        String(20), server_default="standalone", default="standalone", nullable=False
    )  # standalone | parent | branch
    parent_org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    members: Mapped[list["OrganizationMember"]] = relationship(
        "OrganizationMember", back_populates="organization"
    )


class OrganizationMember(Base):
    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint("org_id", "user_id", name="uq_organization_members_org_user"),
    )

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
    # v25 — per-user push notification opt-outs. Default TRUE so new
    # members receive notifications; users silence individual channels
    # from the mobile/web settings page.
    push_stockout_enabled: Mapped[bool] = mapped_column(
        Boolean, server_default="true", default=True, nullable=False
    )
    push_overdue_enabled: Mapped[bool] = mapped_column(
        Boolean, server_default="true", default=True, nullable=False
    )
    push_portal_order_enabled: Mapped[bool] = mapped_column(
        Boolean, server_default="true", default=True, nullable=False
    )
    # Module access mode: "ALL" = sees everything their plan allows (default for owner/admin),
    # "RESTRICTED" = only sees modules listed in member_modules table.
    module_access_mode: Mapped[str] = mapped_column(
        String(20), server_default="ALL", default="ALL", nullable=False
    )
    # POS PIN: bcrypt hash of the 6-digit PIN the cashier uses to log in to
    # the tablet POS. NULL means this member has no POS access via PIN.
    pos_pin_hash: Mapped[str | None] = mapped_column(String(100), nullable=True)
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


class OrgIpAllowlistEntry(Base):
    """One CIDR (or /32 bare IP) on an organization's IP allowlist (Item 25).

    Presence semantics: if an org has ≥ 1 entry in this table, every
    authenticated request for that org is rejected unless the caller's
    IP matches at least one entry. Zero entries == allowlist disabled.

    CIDR is validated in the router layer via the stdlib ``ipaddress``
    module before insert. Stored as TEXT (not Postgres ``cidr``) so the
    Python ORM stays portable and the service layer retains full control
    over parse + match semantics.
    """
    __tablename__ = "org_ip_allowlist"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    cidr:  Mapped[str]        = mapped_column(String(64), nullable=False)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )


class SubscriptionPause(Base):
    """v61 (Item 50) — append-only history row per subscription
    pause. One row per pause window; ``ended_at`` NULL means the
    pause is still active.
    """
    __tablename__ = "subscription_pauses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    scheduled_resume_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    resume_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
