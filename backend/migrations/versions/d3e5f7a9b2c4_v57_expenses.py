"""v57 — expense tracking (Item 43).

Two new tables:

* ``expense_categories`` — per-org taxonomy for expenses. Seeded
  lazily (first ``create_default_categories`` call) so a brand-new
  tenant sees sensible defaults (Travel, Office, Meals, Software,
  Other). ``is_default`` marks the "fallback category" so an
  uncategorised upload always lands somewhere.
* ``expenses`` — one row per logged expense. Carries a three-state
  approval workflow (DRAFT → APPROVED/REJECTED) so a staff member
  can submit expenses that an owner reviews. Receipt upload is
  stored as an external URL (S3/object store) with a small
  metadata side-car (``receipt_mime``, ``receipt_size``) so the
  list view can render a thumbnail without a HEAD round-trip.

Spec suggested v49; v49 is already occupied by
``a7b8c9d0e1f2_v49_gift_cards_bundles.py``. Landed at v57 — chains
from v56 invoice templates. Same convention as §69–§71.

Revision: d3e5f7a9b2c4
Revises:  c2d4e6f8a1b3 (v56 — invoice templates, Item 42)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "d3e5f7a9b2c4"
down_revision = "c2d4e6f8a1b3"
branch_labels = None
depends_on = None


EXPENSE_STATUS_ENUM_NAME = "expense_status"


def upgrade() -> None:
    # Three-state approval workflow. Draft rows are still visible to
    # the submitter; APPROVED rows are locked from edit (enforced at
    # the router layer). REJECTED rows carry the reviewer reason in
    # the ``review_note`` column so the submitter can fix and resubmit.
    status = postgresql.ENUM(
        "DRAFT", "APPROVED", "REJECTED",
        name=EXPENSE_STATUS_ENUM_NAME,
    )
    status.create(op.get_bind(), checkfirst=True)

    # ─────────────────────────────────────────────────────────────
    # expense_categories
    # ─────────────────────────────────────────────────────────────
    op.create_table(
        "expense_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=80), nullable=False),
        # Hex color for the UI chip. Validated at the pydantic layer.
        sa.Column(
            "color",
            sa.String(length=7), nullable=False, server_default="#64748b",
        ),
        # SIE4 account number the category maps to. Optional — orgs
        # without an accounting export still log expenses, and the
        # SIE4 exporter falls back to 6990 (generic other costs).
        sa.Column("sie_account", sa.String(length=10), nullable=True),
        sa.Column(
            "is_default",
            sa.Boolean, nullable=False, server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # One default category per org (partial unique index). Mirror of
    # the invoice_templates pattern in v56 — enforced in SQL so a
    # race between two concurrent "set as default" calls never
    # produces two defaults.
    op.create_index(
        "ux_expense_categories_one_default",
        "expense_categories",
        ["org_id"],
        unique=True,
        postgresql_where=sa.text("is_default = true"),
    )
    op.create_index(
        "ix_expense_categories_org",
        "expense_categories",
        ["org_id"],
    )
    # Case-insensitive uniqueness on (org_id, name). Keeps the UI
    # picker clean; a second "Travel" under the same org is a
    # confusing duplicate, not two distinct expense buckets.
    op.create_index(
        "ux_expense_categories_org_name",
        "expense_categories",
        ["org_id", sa.text("lower(name)")],
        unique=True,
    )

    # ─────────────────────────────────────────────────────────────
    # expenses
    # ─────────────────────────────────────────────────────────────
    op.create_table(
        "expenses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            # Keep the submitter id even if the user row is deleted
            # (orgs can require audit of terminated staff expenses).
            nullable=True,
        ),
        sa.Column(
            "category_id",
            postgresql.UUID(as_uuid=True),
            # ON DELETE SET NULL — deleting a category doesn't destroy
            # the history; it just de-categorises the row so the
            # analytics breakdown shows "Uncategorised".
            sa.ForeignKey("expense_categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "currency",
            sa.String(length=3), nullable=False, server_default="SEK",
        ),
        sa.Column("description", sa.Text, nullable=True),
        # Expense date, as opposed to created_at. Business rule: the
        # analytics breakdown groups by this date, not by when the
        # receipt was uploaded.
        sa.Column("expense_date", sa.Date, nullable=False),
        # Object-store URL. Kept as a string so an S3 rotation
        # doesn't require a schema change. Validated at the router
        # layer to http(s)://.
        sa.Column("receipt_url", sa.String(length=2048), nullable=True),
        sa.Column("receipt_mime", sa.String(length=120), nullable=True),
        sa.Column("receipt_size", sa.Integer, nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                name=EXPENSE_STATUS_ENUM_NAME, create_type=False,
            ),
            nullable=False,
            server_default="DRAFT",
        ),
        sa.Column(
            "approved_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "approved_at",
            sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column("review_note", sa.Text, nullable=True),
        sa.Column(
            "supplier_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("suppliers.id", ondelete="SET NULL"),
            nullable=True,
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
    # Row-level scoping for the staff "my expenses" list.
    op.create_index(
        "ix_expenses_org_created_by",
        "expenses",
        ["org_id", "created_by"],
    )
    # Analytics breakdown by date range + category.
    op.create_index(
        "ix_expenses_org_date",
        "expenses",
        ["org_id", "expense_date"],
    )
    # Approval queue — partial index keeps the hot set tiny.
    op.create_index(
        "ix_expenses_pending_approval",
        "expenses",
        ["org_id", "created_at"],
        postgresql_where=sa.text("status = 'DRAFT'"),
    )


def downgrade() -> None:
    op.drop_index("ix_expenses_pending_approval", table_name="expenses")
    op.drop_index("ix_expenses_org_date", table_name="expenses")
    op.drop_index("ix_expenses_org_created_by", table_name="expenses")
    op.drop_table("expenses")

    op.drop_index(
        "ux_expense_categories_org_name",
        table_name="expense_categories",
    )
    op.drop_index(
        "ix_expense_categories_org",
        table_name="expense_categories",
    )
    op.drop_index(
        "ux_expense_categories_one_default",
        table_name="expense_categories",
    )
    op.drop_table("expense_categories")

    sa.Enum(name=EXPENSE_STATUS_ENUM_NAME).drop(op.get_bind(), checkfirst=True)
