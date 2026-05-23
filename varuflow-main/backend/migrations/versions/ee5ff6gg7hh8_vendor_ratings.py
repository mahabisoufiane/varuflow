"""vendor ratings: create vendor_manual_ratings and vendor_rating_cache tables

Revision ID: ee5ff6gg7hh8
Revises: dd4ee5ff6gg7
Create Date: 2026-05-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "ee5ff6gg7hh8"
down_revision = "dd4ee5ff6gg7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vendor_manual_ratings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("supplier_id", UUID(as_uuid=True), sa.ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("purchase_order_id", UUID(as_uuid=True), nullable=True),
        sa.Column("stars", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("rated_by_staff_id", UUID(as_uuid=True), nullable=True),
        sa.Column("delivery_ok", sa.Boolean(), nullable=True),
        sa.Column("quality_ok", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_vendor_manual_ratings_org_id", "vendor_manual_ratings", ["org_id"])
    op.create_index("ix_vendor_manual_ratings_supplier_id", "vendor_manual_ratings", ["supplier_id"])

    op.create_table(
        "vendor_rating_cache",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("supplier_id", UUID(as_uuid=True), sa.ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("on_time_rate", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("quality_score", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("price_stability", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("manual_avg", sa.Numeric(3, 2), nullable=False, server_default="0"),
        sa.Column("overall_score", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("po_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_updated", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("org_id", "supplier_id", name="uq_vendor_rating_cache_org_supplier"),
    )
    op.create_index("ix_vendor_rating_cache_org_id", "vendor_rating_cache", ["org_id"])
    op.create_index("ix_vendor_rating_cache_supplier_id", "vendor_rating_cache", ["supplier_id"])


def downgrade() -> None:
    op.drop_table("vendor_rating_cache")
    op.drop_table("vendor_manual_ratings")
