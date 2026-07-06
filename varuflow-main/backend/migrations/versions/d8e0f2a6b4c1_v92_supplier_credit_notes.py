"""v92 — Supplier credit notes (Item 92).

Supplier credit notes mirror customer credit notes (Item 70) but
flow in the opposite direction: a supplier issues a credit to us
(for returns, price adjustments, volume rebates, goods damaged on
arrival, etc.). Each credit is org-scoped, per-supplier, and may
optionally reference a source purchase order. When bound to a PO,
the total issued (non-voided) credit amount is capped at the PO's
``total`` so a supplier cannot credit us more than the PO billed.

Numbering mirrors customer credit notes: on ``/issue`` we mint a
per-tenant sequential ``SCN-YYYY-NNNN`` under ``SELECT … FOR
UPDATE`` on the org row to prevent duplicate numbers under
concurrent issuance.

Status machine:
    DRAFT  → ISSUED  → VOIDED
    DRAFT  → VOIDED

Revision: d8e0f2a6b4c1
Revises:  c6d8e0f2a4b9 (v91 — purchase_order_tags, Item 90)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "d8e0f2a6b4c1"
down_revision = "c6d8e0f2a4b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    supplier_credit_note_status = sa.Enum(
        "DRAFT", "ISSUED", "VOIDED",
        name="supplier_credit_note_status",
    )

    op.create_table(
        "supplier_credit_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "supplier_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("suppliers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "purchase_order_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("purchase_orders.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("number", sa.String(length=50), nullable=True),
        sa.Column(
            "status", supplier_credit_note_status,
            nullable=False, server_default="DRAFT",
        ),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("currency", sa.String(length=3),
                  nullable=False, server_default="SEK"),
        sa.Column("subtotal", sa.Numeric(14, 2),
                  nullable=False, server_default="0"),
        sa.Column("tax_total", sa.Numeric(14, 2),
                  nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(14, 2),
                  nullable=False, server_default="0"),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("void_reason", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "org_id", "number", name="uq_supplier_credit_notes_org_number"
        ),
    )
    op.create_index(
        "ix_supplier_credit_notes_org_id",
        "supplier_credit_notes", ["org_id"],
    )
    op.create_index(
        "ix_supplier_credit_notes_supplier_id",
        "supplier_credit_notes", ["supplier_id"],
    )
    op.create_index(
        "ix_supplier_credit_notes_purchase_order_id",
        "supplier_credit_notes", ["purchase_order_id"],
    )
    op.create_index(
        "ix_supplier_credit_notes_status",
        "supplier_credit_notes", ["status"],
    )

    op.create_table(
        "supplier_credit_note_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "supplier_credit_note_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("supplier_credit_notes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("quantity", sa.Numeric(10, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "tax_rate", sa.Numeric(5, 2),
            nullable=False, server_default="25.00",
        ),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "position", sa.Integer(),
            nullable=False, server_default="0",
        ),
    )
    op.create_index(
        "ix_supplier_credit_note_lines_supplier_credit_note_id",
        "supplier_credit_note_lines", ["supplier_credit_note_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_supplier_credit_note_lines_supplier_credit_note_id",
        table_name="supplier_credit_note_lines",
    )
    op.drop_table("supplier_credit_note_lines")
    op.drop_index(
        "ix_supplier_credit_notes_status",
        table_name="supplier_credit_notes",
    )
    op.drop_index(
        "ix_supplier_credit_notes_purchase_order_id",
        table_name="supplier_credit_notes",
    )
    op.drop_index(
        "ix_supplier_credit_notes_supplier_id",
        table_name="supplier_credit_notes",
    )
    op.drop_index(
        "ix_supplier_credit_notes_org_id",
        table_name="supplier_credit_notes",
    )
    op.drop_table("supplier_credit_notes")
    sa.Enum(name="supplier_credit_note_status").drop(
        op.get_bind(), checkfirst=True,
    )
