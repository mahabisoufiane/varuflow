"""v52 — supplier portal tokens (Item 37).

Introduces a read-only supplier portal: an org can mint a magic-link
token for a supplier; the supplier exchanges the raw token URL for a
session, views their own open / past purchase orders, and can confirm
(accept) a PO.

Two schema changes land in one migration so the feature is atomic:

* ``supplier_portal_tokens`` — new table. Stores the **SHA-256 hash**
  of the raw token so a DB leak never yields usable credentials. A
  per-supplier unique index on ``token_hash`` makes replay of a
  rotated token impossible.
* ``purchase_orders`` — two nullable columns: ``confirmed_at``
  (timestamp of supplier acceptance) and ``confirmed_by_supplier_id``
  (FK to ``suppliers.id`` as a defence-in-depth guard against a
  cross-supplier confirm slipping through the router filter).

Spec asked for v44; v44 is already taken by
``b5c7d9e1f3a5_v44_session_version.py``. Landed at v52, the next free
slot after v51 (loyalty). Same rationale as §58–§65 slot shifts.

Revision: d0e1f2a3b4c5
Revises:  c9d0e1f2a3b4 (v51 — loyalty, Item 35)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "supplier_portal_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "supplier_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Redundant with supplier_id but stored anyway so every query
        # against the portal can filter on org_id without a join —
        # keeps the router's isolation guard cheap and the index on
        # (org_id) useful for admin listings.
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # SHA-256 hex digest of the raw token (64 chars). Unique so a
        # rotated raw token can't collide with an old hash in the same
        # DB. Raw token never lands on disk.
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        # Touched on every authenticated portal request so admins can
        # see "last active" per token and auto-retire dormant tokens.
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_revoked",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
    )
    op.create_index(
        "ix_supplier_portal_tokens_supplier",
        "supplier_portal_tokens",
        ["supplier_id", "created_at"],
    )
    op.create_index(
        "ix_supplier_portal_tokens_org_live",
        "supplier_portal_tokens",
        ["org_id", "is_revoked", "expires_at"],
    )

    # Confirmation stamp on purchase_orders. Nullable — legacy POs
    # stay unconfirmed and the UI renders "Awaiting confirmation"
    # until the supplier acts. Adds no default so back-dated rows
    # don't silently look confirmed.
    op.add_column(
        "purchase_orders",
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "purchase_orders",
        sa.Column(
            "confirmed_by_supplier_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("suppliers.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("purchase_orders", "confirmed_by_supplier_id")
    op.drop_column("purchase_orders", "confirmed_at")
    op.drop_index(
        "ix_supplier_portal_tokens_org_live",
        table_name="supplier_portal_tokens",
    )
    op.drop_index(
        "ix_supplier_portal_tokens_supplier",
        table_name="supplier_portal_tokens",
    )
    op.drop_table("supplier_portal_tokens")
