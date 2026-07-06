"""v76 — Customer referral program (Item 68).

Existing customers share a unique referral code; anyone who signs
up / places their first invoice with that code grants the referrer
a reward (points / credit) once the referee's first invoice is
paid.

Two tables:
* ``referral_codes`` — one code per customer (UNIQUE). Codes are
  short, upper-case, alphanumeric, 8 chars.
* ``referrals`` — tracks the (referrer, referee) pair through its
  lifecycle: PENDING → QUALIFIED → REWARDED (+ REJECTED terminal).

Revision: f7a9b1c3d6e7
Revises:  e6f8a0b2c5d6 (v75 — shifts, Item 67)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f7a9b1c3d6e7"
down_revision = "e6f8a0b2c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    referral_status = sa.Enum(
        "PENDING", "QUALIFIED", "REWARDED", "REJECTED",
        name="referral_status",
    )

    op.create_table(
        "referral_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        # One code per customer — idempotent issuance.
        sa.UniqueConstraint(
            "customer_id", name="uq_referral_codes_customer"
        ),
        # Per-org unique code so codes are short enough to say aloud
        # without clashing across customers.
        sa.UniqueConstraint(
            "org_id", "code", name="uq_referral_codes_org_code"
        ),
    )

    op.create_table(
        "referrals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "referrer_customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "referee_customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column(
            "status", referral_status,
            nullable=False, server_default="PENDING",
        ),
        sa.Column(
            "reward_amount", sa.Numeric(12, 2),
            nullable=False, server_default=sa.text("0"),
        ),
        sa.Column("qualified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rewarded_at",  sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at",  sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        # A referee can only be claimed once per org (self-join over
        # the same customer row is rejected by the service).
        sa.UniqueConstraint(
            "org_id", "referee_customer_id",
            name="uq_referrals_org_referee",
        ),
    )
    op.create_index("ix_referrals_org", "referrals", ["org_id"])
    op.create_index(
        "ix_referrals_referrer", "referrals",
        ["org_id", "referrer_customer_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_referrals_referrer", table_name="referrals")
    op.drop_index("ix_referrals_org", table_name="referrals")
    op.drop_table("referrals")
    op.drop_table("referral_codes")
    sa.Enum(name="referral_status").drop(op.get_bind(), checkfirst=True)
