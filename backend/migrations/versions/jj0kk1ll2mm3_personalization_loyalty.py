"""Personalization and Loyalty & Rewards Beyond Points.

Revision ID: jj0kk1ll2mm3
Revises:     ii9jj0kk1ll2
Create Date: 2026-05-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "jj0kk1ll2mm3"
down_revision = "ii9jj0kk1ll2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Personalization ──────────────────────────────────────────────────────────

    op.create_table(
        "customer_preferences",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("favorite_staff_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("preferred_time_of_day", sa.String(20), nullable=True),
        # morning / afternoon / evening / any
        sa.Column("preferred_day_of_week", sa.Integer(), nullable=True),
        # 0=Mon, 6=Sun
        sa.Column("allergies", sa.Text(), nullable=True),
        sa.Column("communication_channel", sa.String(20), nullable=False,
                  server_default="push"),
        # push / email / sms / none
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("org_id", "customer_id",
                            name="uq_customer_preferences_org_customer"),
    )
    op.create_index("ix_customer_preferences_org_id", "customer_preferences", ["org_id"])
    op.create_index("ix_customer_preferences_customer_id",
                    "customer_preferences", ["customer_id"])

    op.create_table(
        "ai_recommendations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), nullable=True),
        sa.Column("service_id", UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("score", sa.Numeric(5, 4), nullable=True),
        sa.Column("is_shown", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_accepted", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_ai_recommendations_org_id", "ai_recommendations", ["org_id"])
    op.create_index("ix_ai_recommendations_customer_id",
                    "ai_recommendations", ["customer_id"])

    op.create_table(
        "customer_important_dates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        # birthday / anniversary / other
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("send_greeting", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("send_discount", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("discount_pct", sa.Integer(), nullable=True),
        sa.Column("last_triggered_year", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("org_id", "customer_id", "label",
                            name="uq_customer_important_dates_org_customer_label"),
    )
    op.create_index("ix_customer_important_dates_org_id",
                    "customer_important_dates", ["org_id"])
    op.create_index("ix_customer_important_dates_date",
                    "customer_important_dates", ["date"])

    op.create_table(
        "saved_payment_methods",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False, server_default="stripe"),
        sa.Column("card_last4", sa.String(4), nullable=True),
        sa.Column("card_brand", sa.String(20), nullable=True),
        sa.Column("card_exp_month", sa.Integer(), nullable=True),
        sa.Column("card_exp_year", sa.Integer(), nullable=True),
        sa.Column("provider_payment_method_id", sa.String(200), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("nickname", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_saved_payment_methods_org_id", "saved_payment_methods", ["org_id"])
    op.create_index("ix_saved_payment_methods_customer_id",
                    "saved_payment_methods", ["customer_id"])

    op.create_table(
        "customer_staff_notes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("staff_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("note_text", sa.Text(), nullable=False),
        sa.Column("is_visible_to_customer", sa.Boolean(), nullable=False,
                  server_default="false"),
        sa.Column("confirmed_by_customer_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_customer_staff_notes_org_id", "customer_staff_notes", ["org_id"])
    op.create_index("ix_customer_staff_notes_customer_id",
                    "customer_staff_notes", ["customer_id"])

    # ── Loyalty & Rewards ────────────────────────────────────────────────────────

    op.create_table(
        "membership_tiers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("min_points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("card_color", sa.String(7), nullable=False, server_default="#CD7F32"),
        sa.Column("card_text_color", sa.String(7), nullable=False, server_default="#FFFFFF"),
        sa.Column("benefits", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_membership_tiers_org_id", "membership_tiers", ["org_id"])

    op.create_table(
        "customer_memberships",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("tier_id", UUID(as_uuid=True),
                  sa.ForeignKey("membership_tiers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("awarded_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("org_id", "customer_id",
                            name="uq_customer_memberships_org_customer"),
    )
    op.create_index("ix_customer_memberships_org_id", "customer_memberships", ["org_id"])
    op.create_index("ix_customer_memberships_customer_id",
                    "customer_memberships", ["customer_id"])

    op.create_table(
        "achievements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("badge_icon", sa.String(100), nullable=True),
        sa.Column("badge_color", sa.String(7), nullable=False, server_default="#FFD700"),
        sa.Column("trigger_type", sa.String(50), nullable=False),
        # visit_count / month_streak / first_of_month / spend_amount / referrals
        sa.Column("trigger_value", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_achievements_org_id", "achievements", ["org_id"])

    op.create_table(
        "customer_achievements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("achievement_id", UUID(as_uuid=True),
                  sa.ForeignKey("achievements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("awarded_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_customer_achievements_org_id", "customer_achievements", ["org_id"])
    op.create_index("ix_customer_achievements_customer_id",
                    "customer_achievements", ["customer_id"])

    op.create_table(
        "birthday_vouchers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("voucher_code", sa.String(20), nullable=False, unique=True),
        sa.Column("discount_type", sa.String(20), nullable=False, server_default="pct"),
        # pct / fixed
        sa.Column("discount_value", sa.Numeric(10, 2), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=False),
        sa.Column("is_redeemed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("generated_for_year", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_birthday_vouchers_org_id", "birthday_vouchers", ["org_id"])
    op.create_index("ix_birthday_vouchers_customer_id",
                    "birthday_vouchers", ["customer_id"])
    op.create_index("ix_birthday_vouchers_code", "birthday_vouchers", ["voucher_code"],
                    unique=True)

    op.create_table(
        "referral_tracking",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("referrer_customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("referred_customer_id", UUID(as_uuid=True), nullable=True),
        sa.Column("referral_code", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        # pending / qualified / rewarded
        sa.Column("reward_points", sa.Integer(), nullable=True),
        sa.Column("qualified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("org_id", "referrer_customer_id", "referred_customer_id",
                            name="uq_referral_tracking_org_referrer_referred"),
    )
    op.create_index("ix_referral_tracking_org_id", "referral_tracking", ["org_id"])
    op.create_index("ix_referral_tracking_referrer_id",
                    "referral_tracking", ["referrer_customer_id"])
    op.create_index("ix_referral_tracking_code", "referral_tracking", ["referral_code"])

    op.create_table(
        "loyalty_streaks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("streak_type", sa.String(30), nullable=False),
        # monthly_visit / weekly_visit
        sa.Column("current_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("longest_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_activity_date", sa.Date(), nullable=True),
        sa.Column("streak_start_date", sa.Date(), nullable=True),
        sa.Column("milestone_rewards", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("org_id", "customer_id", "streak_type",
                            name="uq_loyalty_streaks_org_customer_type"),
    )
    op.create_index("ix_loyalty_streaks_org_id", "loyalty_streaks", ["org_id"])
    op.create_index("ix_loyalty_streaks_customer_id", "loyalty_streaks", ["customer_id"])


def downgrade() -> None:
    op.drop_table("loyalty_streaks")
    op.drop_table("referral_tracking")
    op.drop_table("birthday_vouchers")
    op.drop_table("customer_achievements")
    op.drop_table("achievements")
    op.drop_table("customer_memberships")
    op.drop_table("membership_tiers")
    op.drop_table("customer_staff_notes")
    op.drop_table("saved_payment_methods")
    op.drop_table("customer_important_dates")
    op.drop_table("ai_recommendations")
    op.drop_table("customer_preferences")
