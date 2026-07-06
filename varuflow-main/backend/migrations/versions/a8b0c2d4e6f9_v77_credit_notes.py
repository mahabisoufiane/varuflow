"""v77 — Customer credit notes (Item 70).

Credit notes are signed, numbered documents that reduce what a
customer owes. Unlike a raw invoice adjustment, credit notes are
archived for bokföringslagen and can be exported to Fortnox / SIE4
as their own accounting transaction. A single credit note can
either:

* Be issued **against a specific invoice** — the credited amount
  reduces the invoice's outstanding balance; an invoice marked PAID
  by a credit note stays PAID (payments + credits ≥ total).
* Stand **alone** — e.g. a goodwill voucher without an underlying
  invoice. ``invoice_id`` is then NULL.

Status machine:
    DRAFT  → ISSUED  → VOIDED
    DRAFT  → VOIDED

Issuing a credit note mints the per-org sequential number
``CN-YYYY-NNNN`` and locks the line items (they become immutable).
Voiding is reversible only by creating a fresh credit note.

Revision: a8b0c2d4e6f9
Revises:  f7a9b1c3d6e7 (v76 — referrals, Item 68)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "a8b0c2d4e6f9"
down_revision = "f7a9b1c3d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    credit_note_status = sa.Enum(
        "DRAFT", "ISSUED", "VOIDED",
        name="credit_note_status",
    )

    op.create_table(
        "credit_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "invoice_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoices.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("number", sa.String(length=50), nullable=True),
        sa.Column(
            "status", credit_note_status,
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
        # Mirrors the invoices table — concurrent issue of two credit
        # notes inside the same tenant must not mint the same number.
        sa.UniqueConstraint(
            "org_id", "number", name="uq_credit_notes_org_number"
        ),
    )
    op.create_index(
        "ix_credit_notes_org_id", "credit_notes", ["org_id"],
    )
    op.create_index(
        "ix_credit_notes_customer_id", "credit_notes", ["customer_id"],
    )
    op.create_index(
        "ix_credit_notes_invoice_id", "credit_notes", ["invoice_id"],
    )
    op.create_index(
        "ix_credit_notes_status", "credit_notes", ["status"],
    )

    op.create_table(
        "credit_note_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "credit_note_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("credit_notes.id", ondelete="CASCADE"),
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
        "ix_credit_note_lines_credit_note_id",
        "credit_note_lines", ["credit_note_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_credit_note_lines_credit_note_id",
                  table_name="credit_note_lines")
    op.drop_table("credit_note_lines")
    op.drop_index("ix_credit_notes_status", table_name="credit_notes")
    op.drop_index("ix_credit_notes_invoice_id", table_name="credit_notes")
    op.drop_index("ix_credit_notes_customer_id", table_name="credit_notes")
    op.drop_index("ix_credit_notes_org_id", table_name="credit_notes")
    op.drop_table("credit_notes")
    sa.Enum(name="credit_note_status").drop(op.get_bind(), checkfirst=True)
