"""CRM pipeline v2: custom deal stages, win/loss reasons, quote/invoice links, sales cycle

Revision ID: aa1bb2cc3dd4
Revises: z3t4u5v6w7x8
Create Date: 2026-04-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "aa1bb2cc3dd4"
down_revision = "z3t4u5v6w7x8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Custom deal stages per org ─────────────────────────────────────────
    # If an org has rows here, the board uses these stages instead of defaults.
    # is_won / is_lost tell the app whether closing into this stage counts as a win.
    op.create_table(
        "deal_stages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(50), nullable=False),
        sa.Column("color", sa.String(20), nullable=True),   # Tailwind bg color token
        sa.Column("order_idx", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_won", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_lost", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_deal_stages_org_id", "deal_stages", ["org_id"])
    op.create_unique_constraint("uq_deal_stages_org_slug", "deal_stages", ["org_id", "slug"])

    # ── Deals: new columns ─────────────────────────────────────────────────
    # Win/loss reason captured when a deal is closed.
    op.add_column("deals", sa.Column("win_reason", sa.Text(), nullable=True))
    op.add_column("deals", sa.Column("loss_reason", sa.Text(), nullable=True))

    # Timestamp when the deal moved to a terminal stage (won/lost).
    # sales_cycle_days = (closed_at - created_at).days — computed at read time.
    op.add_column("deals", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))

    # Optional link to a quote that was sent as part of this deal.
    # The FK to quotes.id is added later in ee4ff5gg6hh7 (portal_quotes), which
    # creates the `quotes` table and is a DESCENDANT of this migration. Declaring
    # the FK inline here fails a fresh `alembic upgrade head` — `quotes` does not
    # exist yet at this point in the migration DAG.
    op.add_column("deals", sa.Column(
        "quote_id", UUID(as_uuid=True),
        nullable=True,
    ))

    # Optional link to the invoice created when the deal was won.
    op.add_column("deals", sa.Column(
        "invoice_id", UUID(as_uuid=True),
        sa.ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
    ))

    op.create_index("ix_deals_quote_id", "deals", ["quote_id"])
    op.create_index("ix_deals_invoice_id", "deals", ["invoice_id"])
    op.create_index("ix_deals_closed_at", "deals", ["closed_at"])


def downgrade() -> None:
    op.drop_index("ix_deals_closed_at", "deals")
    op.drop_index("ix_deals_invoice_id", "deals")
    op.drop_index("ix_deals_quote_id", "deals")
    op.drop_column("deals", "invoice_id")
    op.drop_column("deals", "quote_id")
    op.drop_column("deals", "closed_at")
    op.drop_column("deals", "loss_reason")
    op.drop_column("deals", "win_reason")
    op.drop_constraint("uq_deal_stages_org_slug", "deal_stages", type_="unique")
    op.drop_table("deal_stages")
