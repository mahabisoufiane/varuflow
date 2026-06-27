"""v103 – operator_referrals table

Revision ID: b2o3p4r5e6f7
Revises: a1b2p3a4r5t6
Create Date: 2026-05-02
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b2o3p4r5e6f7"
down_revision = "a1b2p3a4r5t6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operator_referrals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("referrer_org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("referrer_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("referee_org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("referral_code", sa.String(30), nullable=False),
        sa.Column("referral_method", sa.String(20), nullable=False, server_default="link"),
        sa.Column("reward_type", sa.String(20), nullable=False, server_default="commission"),
        sa.Column("commission_rate_pct", sa.Numeric(5, 2), nullable=False, server_default="20"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("clicked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("signed_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("months_remaining", sa.Integer, nullable=False, server_default="12"),
        sa.Column("subscription_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("commission_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("stripe_coupon_id", sa.String(200), nullable=True),
        sa.Column("stripe_payout_id", sa.String(200), nullable=True),
        sa.Column("referrer_email_hash", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("referral_code", name="uq_opr_referral_code"),
    )
    op.create_index("ix_opr_referrer_org_id", "operator_referrals", ["referrer_org_id"])
    op.create_index("ix_opr_referee_org_id", "operator_referrals", ["referee_org_id"])
    op.create_index("ix_opr_status", "operator_referrals", ["status"])
    op.create_index("ix_opr_referral_code", "operator_referrals", ["referral_code"])


def downgrade() -> None:
    op.drop_index("ix_opr_referral_code", "operator_referrals")
    op.drop_index("ix_opr_status", "operator_referrals")
    op.drop_index("ix_opr_referee_org_id", "operator_referrals")
    op.drop_index("ix_opr_referrer_org_id", "operator_referrals")
    op.drop_table("operator_referrals")
