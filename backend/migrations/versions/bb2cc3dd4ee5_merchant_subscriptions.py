"""Merchant subscription billing

Revision ID: bb2cc3dd4ee5
Revises: aa1bb2cc3dd4
Create Date: 2026-05-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "bb2cc3dd4ee5"
down_revision = "aa1bb2cc3dd4"
branch_labels = None
depends_on = None


def upgrade():
    # merchant_subscription_plans — reusable billing plans defined per org
    op.create_table(
        "merchant_subscription_plans",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("price", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="SEK"),
        sa.Column("interval", sa.String(20), nullable=False, server_default="monthly"),
        sa.Column("interval_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("stripe_price_id", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("trial_days", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_merchant_subscription_plans_org_id",
        "merchant_subscription_plans",
        ["org_id"],
    )

    # merchant_subscriptions — customer subscriptions to a plan
    op.create_table(
        "merchant_subscriptions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("merchant_subscription_plans.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stripe_subscription_id", sa.String(100), nullable=True),
        sa.Column("stripe_customer_id", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("trial_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resume_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notice_period_days", sa.Integer, nullable=False, server_default="30"),
        sa.Column("proration_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_merchant_subscriptions_org_id", "merchant_subscriptions", ["org_id"]
    )
    op.create_index(
        "ix_merchant_subscriptions_customer_id",
        "merchant_subscriptions",
        ["customer_id"],
    )
    op.create_index(
        "ix_merchant_subscriptions_plan_id", "merchant_subscriptions", ["plan_id"]
    )
    # Unique index on stripe_subscription_id where not null
    op.create_index(
        "ix_merchant_subscriptions_stripe_sub_id",
        "merchant_subscriptions",
        ["stripe_subscription_id"],
        unique=True,
        postgresql_where=sa.text("stripe_subscription_id IS NOT NULL"),
    )


def downgrade():
    op.drop_table("merchant_subscriptions")
    op.drop_table("merchant_subscription_plans")
