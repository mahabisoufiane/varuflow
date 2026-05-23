"""mob1 - mobile and field operations

Revision ID: z3t4u5v6w7x8
Revises: y2s3t4u5v6w7
Create Date: 2026-04-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "z3t4u5v6w7x8"
down_revision = "y2s3t4u5v6w7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "delivery_routes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("driver_name", sa.String(100), nullable=True),
        sa.Column("route_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),  # draft|active|completed
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "route_stops",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("route_id", UUID(as_uuid=True), sa.ForeignKey("delivery_routes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("stop_type", sa.String(20), nullable=False),  # customer|warehouse|supplier|custom
        sa.Column("ref_id", UUID(as_uuid=True), nullable=True),  # customer_id / supplier_id / warehouse_id
        sa.Column("label", sa.String(200), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("lat", sa.Numeric(9, 6), nullable=True),
        sa.Column("lng", sa.Numeric(9, 6), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),  # pending|visited|skipped
        sa.Column("arrived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "digital_signatures",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("signer_name", sa.String(200), nullable=False),
        sa.Column("signer_role", sa.String(100), nullable=True),  # customer|driver|technician
        sa.Column("document_type", sa.String(50), nullable=False),  # delivery_note|contract|invoice|other
        sa.Column("ref_id", UUID(as_uuid=True), nullable=True),  # invoice_id / order_id / route_id
        sa.Column("svg_data", sa.Text(), nullable=False),  # SVG path data of signature
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("signed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "stripe_terminal_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("reader_id", sa.String(200), nullable=True),  # Stripe Terminal reader ID
        sa.Column("payment_intent_id", sa.String(200), nullable=True, index=True),
        sa.Column("invoice_id", UUID(as_uuid=True), sa.ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="SEK"),
        sa.Column("status", sa.String(30), nullable=False, server_default="initiated"),  # initiated|processing|succeeded|failed|canceled
        sa.Column("stripe_response", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "voice_notes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("entity_type", sa.String(30), nullable=False),  # customer|supplier|route_stop|invoice
        sa.Column("entity_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("file_url", sa.Text(), nullable=False),  # storage URL (Supabase Storage)
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("transcription", sa.Text(), nullable=True),  # Whisper transcription if available
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("voice_notes")
    op.drop_table("stripe_terminal_sessions")
    op.drop_table("digital_signatures")
    op.drop_table("route_stops")
    op.drop_table("delivery_routes")
