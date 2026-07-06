"""Convenience & B2B Buyer Features.

Revision ID: kk1ll2mm3nn4
Revises:     jj0kk1ll2mm3
Create Date: 2026-05-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "kk1ll2mm3nn4"
down_revision = "jj0kk1ll2mm3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Convenience ───────────────────────────────────────────────────────────────

    op.create_table(
        "customer_addresses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(50), nullable=False, server_default="home"),
        # home / office / other / custom label
        sa.Column("line1", sa.String(200), nullable=False),
        sa.Column("line2", sa.String(200), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("state", sa.String(100), nullable=True),
        sa.Column("postal_code", sa.String(20), nullable=True),
        sa.Column("country", sa.String(2), nullable=False, server_default="SE"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("org_id", "customer_id", "label",
                            name="uq_customer_addresses_org_customer_label"),
    )
    op.create_index("ix_customer_addresses_org_id", "customer_addresses", ["org_id"])
    op.create_index("ix_customer_addresses_customer_id", "customer_addresses", ["customer_id"])

    op.create_table(
        "calendar_sync_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False, server_default="ical"),
        # ical / google
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("token_expiry", sa.DateTime(timezone=True), nullable=True),
        sa.Column("calendar_id", sa.String(200), nullable=True),
        sa.Column("sync_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("org_id", "customer_id", "provider",
                            name="uq_calendar_sync_tokens_org_customer_provider"),
    )
    op.create_index("ix_calendar_sync_tokens_org_id", "calendar_sync_tokens", ["org_id"])
    op.create_index("ix_calendar_sync_tokens_customer_id",
                    "calendar_sync_tokens", ["customer_id"])

    op.create_table(
        "accountant_forwarding",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("accountant_email", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("org_id", "customer_id",
                            name="uq_accountant_forwarding_org_customer"),
    )
    op.create_index("ix_accountant_forwarding_org_id", "accountant_forwarding", ["org_id"])
    op.create_index("ix_accountant_forwarding_customer_id",
                    "accountant_forwarding", ["customer_id"])

    op.create_table(
        "receipt_exports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", UUID(as_uuid=True),
                  sa.ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("export_target", sa.String(30), nullable=False),
        # splitwise / personal_capital / ynab / csv
        sa.Column("exported_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("export_ref", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_receipt_exports_org_id", "receipt_exports", ["org_id"])
    op.create_index("ix_receipt_exports_customer_id", "receipt_exports", ["customer_id"])

    op.create_table(
        "wallet_payment_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", UUID(as_uuid=True),
                  sa.ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="SEK"),
        sa.Column("provider", sa.String(20), nullable=False),
        # apple_pay / google_pay
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        # pending / completed / failed
        sa.Column("provider_session_id", sa.String(200), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_wallet_payment_sessions_org_id", "wallet_payment_sessions", ["org_id"])
    op.create_index("ix_wallet_payment_sessions_customer_id",
                    "wallet_payment_sessions", ["customer_id"])

    # ── B2B Buyer ─────────────────────────────────────────────────────────────────

    op.create_table(
        "buyer_purchase_orders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("buyer_po_number", sa.String(100), nullable=False),
        sa.Column("buyer_org_name", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        # draft / submitted / confirmed / rejected / fulfilled
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("requested_delivery_date", sa.Date(), nullable=True),
        sa.Column("confirmed_by_staff_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_buyer_purchase_orders_org_id", "buyer_purchase_orders", ["org_id"])
    op.create_index("ix_buyer_purchase_orders_customer_id",
                    "buyer_purchase_orders", ["customer_id"])
    op.create_index("ix_buyer_purchase_orders_status", "buyer_purchase_orders", ["status"])

    op.create_table(
        "buyer_po_line_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("buyer_po_id", UUID(as_uuid=True),
                  sa.ForeignKey("buyer_purchase_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), nullable=True),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_buyer_po_line_items_po_id", "buyer_po_line_items", ["buyer_po_id"])

    op.create_table(
        "customer_org_members",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        # the "buying organization" customer this member belongs to
        sa.Column("member_email", sa.String(200), nullable=False),
        sa.Column("member_name", sa.String(200), nullable=True),
        sa.Column("role", sa.String(20), nullable=False, server_default="requester"),
        # admin / approver / requester
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("invitation_token", sa.String(100), nullable=True),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("org_id", "customer_id", "member_email",
                            name="uq_customer_org_members_org_customer_email"),
    )
    op.create_index("ix_customer_org_members_org_id", "customer_org_members", ["org_id"])
    op.create_index("ix_customer_org_members_customer_id",
                    "customer_org_members", ["customer_id"])
    op.create_index("ix_customer_org_members_token", "customer_org_members", ["invitation_token"])

    op.create_table(
        "buyer_order_approvals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("buyer_po_id", UUID(as_uuid=True),
                  sa.ForeignKey("buyer_purchase_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_by_member_id", UUID(as_uuid=True),
                  sa.ForeignKey("customer_org_members.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        # pending / approved / rejected
        sa.Column("reviewed_by_member_id", UUID(as_uuid=True),
                  sa.ForeignKey("customer_org_members.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_buyer_order_approvals_org_id", "buyer_order_approvals", ["org_id"])
    op.create_index("ix_buyer_order_approvals_po_id", "buyer_order_approvals", ["buyer_po_id"])

    op.create_table(
        "quote_comparisons",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("quote_ids", JSONB(), nullable=False, server_default="[]"),
        # array of quote UUIDs from different suppliers
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_quote_comparisons_org_id", "quote_comparisons", ["org_id"])
    op.create_index("ix_quote_comparisons_customer_id", "quote_comparisons", ["customer_id"])


def downgrade() -> None:
    op.drop_table("quote_comparisons")
    op.drop_table("buyer_order_approvals")
    op.drop_table("customer_org_members")
    op.drop_table("buyer_po_line_items")
    op.drop_table("buyer_purchase_orders")
    op.drop_table("wallet_payment_sessions")
    op.drop_table("receipt_exports")
    op.drop_table("accountant_forwarding")
    op.drop_table("calendar_sync_tokens")
    op.drop_table("customer_addresses")
