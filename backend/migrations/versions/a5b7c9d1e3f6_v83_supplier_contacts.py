"""v83 — Supplier contacts (Item 78).

Multiple contact persons per supplier — each with role, encrypted
email/phone, and an ``is_primary`` flag that is mutually exclusive
per supplier (enforced by a partial unique index). Used by the
purchasing flow: POs get emailed to the primary contact, RFQs CC
every contact with ``receives_rfq=true``, etc.

Revision: a5b7c9d1e3f6
Revises:  f4a6b8d0c2e5 (v82 — supplier tags, Item 77)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "a5b7c9d1e3f6"
down_revision = "f4a6b8d0c2e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "supplier_contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "supplier_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=True),
        # PII — encrypted at rest via EncryptedString, same as
        # suppliers.email / suppliers.phone. The underlying column is
        # a wide String; size is the ciphertext ceiling.
        sa.Column("email", sa.String(length=512), nullable=True),
        sa.Column("phone", sa.String(length=256), nullable=True),
        sa.Column(
            "is_primary", sa.Boolean(),
            nullable=False, server_default=sa.false(),
        ),
        sa.Column(
            "receives_rfq", sa.Boolean(),
            nullable=False, server_default=sa.true(),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_supplier_contacts_supplier_id",
        "supplier_contacts", ["supplier_id"],
    )
    op.create_index(
        "ix_supplier_contacts_org_id",
        "supplier_contacts", ["org_id"],
    )
    # Partial unique index — at most one primary contact per
    # supplier. Using WHERE is_primary so multiple false rows are
    # allowed (a supplier with no primary is valid).
    op.create_index(
        "ux_supplier_contacts_one_primary_per_supplier",
        "supplier_contacts", ["supplier_id"],
        unique=True,
        postgresql_where=sa.text("is_primary = true"),
    )


def downgrade() -> None:
    op.drop_index(
        "ux_supplier_contacts_one_primary_per_supplier",
        table_name="supplier_contacts",
    )
    op.drop_index(
        "ix_supplier_contacts_org_id", table_name="supplier_contacts",
    )
    op.drop_index(
        "ix_supplier_contacts_supplier_id",
        table_name="supplier_contacts",
    )
    op.drop_table("supplier_contacts")
