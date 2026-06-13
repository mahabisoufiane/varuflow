"""v56 — custom invoice templates (Item 42).

Single new table:

* ``invoice_templates`` — one row per branded template an org can
  attach to outgoing invoices. Per-tenant. The ``is_default`` flag
  is enforced as "at most one default per org" via a partial unique
  index (PostgreSQL). ``is_active`` lets a tenant retire a template
  without deleting it, preserving historical attachments on past
  invoices.

Spec suggested v48. v48 is already occupied by commissions.
Shifting to v56 — same convention as Items 40/41 (§69, §70).

Revision: c2d4e6f8a1b3
Revises:  b1c2d3e4f5a6 (v55 — campaigns, Item 40)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c2d4e6f8a1b3"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invoice_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "is_default",
            sa.Boolean, nullable=False, server_default=sa.text("false"),
        ),
        # Logo hosted externally (S3/public URL). Stored as a string
        # so we don't need a second round-trip for rendering. Nullable
        # for text-only templates.
        sa.Column("logo_url", sa.String(length=1024), nullable=True),
        # Hex colors; validated at the pydantic layer. Default values
        # mirror the house brand so a freshly created template still
        # renders a passable invoice without any styling.
        sa.Column(
            "primary_color",
            sa.String(length=7), nullable=False, server_default="#1a2332",
        ),
        sa.Column(
            "accent_color",
            sa.String(length=7), nullable=False, server_default="#2563eb",
        ),
        # Font family label. Enumerated in the renderer; unknown
        # fonts fall back to Helvetica so a stored mis-spelling
        # doesn't break PDF generation.
        sa.Column(
            "font_family",
            sa.String(length=60), nullable=False, server_default="Helvetica",
        ),
        sa.Column(
            "show_bank_details",
            sa.Boolean, nullable=False, server_default=sa.text("true"),
        ),
        sa.Column(
            "show_qr_code",
            sa.Boolean, nullable=False, server_default=sa.text("false"),
        ),
        sa.Column("footer_text", sa.Text, nullable=True),
        sa.Column("header_text", sa.Text, nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean, nullable=False, server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_invoice_templates_org",
        "invoice_templates",
        ["org_id"],
    )
    # Partial unique index: guarantees at most one default template
    # per org. Enforced in SQL so a race between two concurrent
    # "set as default" requests can never produce two defaults.
    op.create_index(
        "ux_invoice_templates_one_default",
        "invoice_templates",
        ["org_id"],
        unique=True,
        postgresql_where=sa.text("is_default = true"),
    )


def downgrade() -> None:
    op.drop_index(
        "ux_invoice_templates_one_default",
        table_name="invoice_templates",
    )
    op.drop_index(
        "ix_invoice_templates_org",
        table_name="invoice_templates",
    )
    op.drop_table("invoice_templates")
