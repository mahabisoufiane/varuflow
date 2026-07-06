"""v45: org-level IP allowlist (Item 25).

Adds a new table ``org_ip_allowlist``:

* ``id UUID PK``
* ``org_id UUID FK organizations.id ON DELETE CASCADE`` — a deleted org
  takes its allowlist with it; a dangling entry would otherwise silently
  reject every request for the recycled org-id on another tenant.
* ``cidr TEXT NOT NULL`` — CIDR or bare IP ("203.0.113.5/32" or
  "203.0.113.0/24"). Stored as TEXT + validated in the service layer;
  Postgres has a native ``cidr`` type but ``TEXT`` keeps the Python
  model portable and lets us add IPv6 / IP-with-host notation later
  without a schema migration.
* ``label TEXT`` — human-readable ("HQ firewall", "Stockholm office").
* ``created_at TIMESTAMPTZ DEFAULT now()``
* ``created_by UUID`` — actor for audit trail.

Additive migration — no existing rows reference the table, and the
runtime enforcement rule is "only deny if the org has >= 1 entry", so
the empty table post-upgrade means every existing tenant continues to
work unchanged.
"""
from alembic import op
import sqlalchemy as sa


revision = "c6d8e0f2a4b6"
down_revision = "b5c7d9e1f3a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "org_ip_allowlist",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            # No index=True here — the explicit op.create_index below already
            # creates ix_org_ip_allowlist_org_id. Having both double-creates the
            # index and fails a fresh upgrade with DuplicateTableError.
        ),
        sa.Column("cidr", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_by",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_org_ip_allowlist_org_id",
        "org_ip_allowlist",
        ["org_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_org_ip_allowlist_org_id", table_name="org_ip_allowlist")
    op.drop_table("org_ip_allowlist")
