"""v48 — Staff commission tracking (Item 32)

Revision ID: f9a1b3c5d7e2
Revises: e8f0a2b4c6d9
Create Date: 2026-04-23

Adds three tables for the commission module:

* ``commission_rules`` — per-staff rules. ``rule_type`` is free-form
  string (``flat`` / ``pct`` / ``tiered``) so future rule kinds ship
  without migrations. ``value`` is the numeric knob whose meaning
  depends on ``rule_type``; ``min_threshold`` gates the rule so a
  tiered "over 10 000 SEK → 8%" rule is one row, not one table.
* ``commission_runs`` — an admin-approved reporting period. Locking
  is a ``status`` flip (``open`` → ``locked``), preventing the router
  from mutating entries after payout.
* ``commission_entries`` — one row per commissionable transaction.
  ``run_id`` may be NULL while the entry sits in the "not yet binned"
  pool that the monthly scheduler sweeps into the active run.

Also adds a nullable ``staff_id`` FK to ``pos_sales`` and ``invoices``
so the POS + invoicing hooks can attribute commission to a salon /
retail staff row without a separate lookup table. Both default NULL,
so existing rows + non-salon tenants are unaffected.

Spec note: the item reserved **v40**; v40 was consumed earlier in the
chain. Following the same deviation convention as Item 31, we land at
the next free slot (v48). The Alembic chain stays strictly linear.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f9a1b3c5d7e2"
down_revision = "e8f0a2b4c6d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── commission_rules ───────────────────────────────────────────────
    op.create_table(
        "commission_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "staff_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            index=True,
        ),
        # flat | pct | tiered
        sa.Column("rule_type", sa.String(16), nullable=False),
        # Interpretation depends on rule_type:
        #   flat   → the fixed amount paid per qualifying transaction
        #   pct    → the percentage (0–100) of base_amount
        #   tiered → the percentage (0–100), gated by min_threshold
        sa.Column("value", sa.Numeric(10, 4), nullable=False),
        # all | service | product | category
        sa.Column(
            "applies_to",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'all'"),
        ),
        sa.Column(
            "min_threshold",
            sa.Numeric(12, 2),
            nullable=True,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ── commission_runs ────────────────────────────────────────────────
    op.create_table(
        "commission_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        # open → locked → paid (locked prevents entry mutation).
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'open'"),
        ),
        sa.Column(
            "total_paid",
            sa.Numeric(12, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── commission_entries ─────────────────────────────────────────────
    op.create_table(
        "commission_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # Nullable: an entry created by a hook before a run exists sits
        # in the "unassigned pool" until the monthly scheduler sweeps it.
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("commission_runs.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "staff_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            index=True,
        ),
        # sale | booking | invoice
        sa.Column("source_type", sa.String(16), nullable=False),
        # UUID string of the source row. Not a real FK because three
        # different tables can produce entries; the shape has to stay
        # polymorphic without a composite reference.
        sa.Column("source_id", sa.String(64), nullable=False),
        sa.Column("base_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("commission_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "rule_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("commission_rules.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # Hot path: "give me every entry for staff X in this run".
    op.create_index(
        "ix_commission_entries_run_staff",
        "commission_entries",
        ["run_id", "staff_id"],
    )

    # ── pos_sales.staff_id (forward-compat, NULL-default) ──────────────
    op.add_column(
        "pos_sales",
        sa.Column(
            "staff_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    # ── invoices.staff_id ─────────────────────────────────────────────
    op.add_column(
        "invoices",
        sa.Column(
            "staff_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("invoices", "staff_id")
    op.drop_column("pos_sales", "staff_id")
    op.drop_index("ix_commission_entries_run_staff", table_name="commission_entries")
    op.drop_table("commission_entries")
    op.drop_table("commission_runs")
    op.drop_table("commission_rules")
