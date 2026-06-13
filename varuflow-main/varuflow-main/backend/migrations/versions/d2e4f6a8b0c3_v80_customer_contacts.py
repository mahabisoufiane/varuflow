"""v80 — Customer contacts (Item 74).

Multiple contact persons per customer — each with role, encrypted
email/phone, and an ``is_primary`` flag that is mutually exclusive
per customer (enforced by a partial unique index). Used by the
CRM features added in Items 70–73: statements get emailed to the
primary contact, dunning CC's all contacts with
``receives_dunning=true``, etc.

Revision: d2e4f6a8b0c3
Revises:  c1d3e5f7a9b2 (v79 — customer tags, Item 73)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "d2e4f6a8b0c3"
down_revision = "c1d3e5f7a9b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=True),
        # PII — encrypted at rest via EncryptedString, same as
        # customers.email / customers.phone (Item 28). The underlying
        # column is a wide String; size is the ciphertext ceiling.
        sa.Column("email", sa.String(length=512), nullable=True),
        sa.Column("phone", sa.String(length=256), nullable=True),
        sa.Column(
            "is_primary", sa.Boolean(),
            nullable=False, server_default=sa.false(),
        ),
        sa.Column(
            "receives_dunning", sa.Boolean(),
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
        "ix_customer_contacts_customer_id",
        "customer_contacts", ["customer_id"],
    )
    op.create_index(
        "ix_customer_contacts_org_id",
        "customer_contacts", ["org_id"],
    )
    # Partial unique index — at most one primary contact per
    # customer. Using WHERE is_primary so multiple false rows are
    # allowed (a customer with no primary is valid).
    op.create_index(
        "ux_customer_contacts_one_primary_per_customer",
        "customer_contacts", ["customer_id"],
        unique=True,
        postgresql_where=sa.text("is_primary = true"),
    )


def downgrade() -> None:
    op.drop_index(
        "ux_customer_contacts_one_primary_per_customer",
        table_name="customer_contacts",
    )
    op.drop_index(
        "ix_customer_contacts_org_id", table_name="customer_contacts",
    )
    op.drop_index(
        "ix_customer_contacts_customer_id",
        table_name="customer_contacts",
    )
    op.drop_table("customer_contacts")
