"""v54 — customer segmentation (Item 39).

Adds two tables:

* ``segments`` — named audiences scoped to an organisation. ``type``
  is either ``AUTO`` (rule-driven, refreshed nightly) or ``MANUAL``
  (membership managed by an operator). ``rules`` is a JSONB blob so
  the schema can evolve without migrations.
* ``segment_members`` — the resolved membership list. For auto
  segments this is recomputed by the scheduler; for manual segments
  operators insert / delete rows directly.

Spec asked for v46; v46 is taken by
``d7e9f1a3b5c7_v46_pii_encryption_widen.py``. Landed at v54 — the
next free slot after v53 (stock transfers, Item 38). Same shift
rationale as §58–§67.

Revision: f1a2b3c4d5e6
Revises:  e1f2a3b4c5d6 (v53 — stock transfers, Item 38)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f1a2b3c4d5e6"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


SEGMENT_TYPE_ENUM_NAME = "segment_type"


def upgrade() -> None:
    seg_type = postgresql.ENUM(
        "AUTO",
        "MANUAL",
        name=SEGMENT_TYPE_ENUM_NAME,
    )
    seg_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "segments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "type",
            postgresql.ENUM(name=SEGMENT_TYPE_ENUM_NAME, create_type=False),
            nullable=False,
        ),
        # Rule payload for AUTO segments — free-form JSONB so the rule
        # language can evolve (add fields, operators) without schema
        # migrations. Ignored for MANUAL segments.
        sa.Column(
            "rules",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "customer_count",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column("last_computed_at", sa.DateTime(timezone=True), nullable=True),
        # Optional actor attribution. Nullable because seed / system
        # segments have no human author.
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("org_id", "name", name="uq_segments_org_name"),
    )
    op.create_index(
        "ix_segments_org_type",
        "segments",
        ["org_id", "type"],
    )

    op.create_table(
        "segment_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "segment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("segments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # A customer is either in the segment or not — duplicate rows
        # would break ``customer_count`` and inflate analytics filters.
        sa.UniqueConstraint(
            "segment_id", "customer_id",
            name="uq_segment_members_segment_customer",
        ),
    )
    op.create_index(
        "ix_segment_members_segment",
        "segment_members",
        ["segment_id"],
    )
    op.create_index(
        "ix_segment_members_customer",
        "segment_members",
        ["customer_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_segment_members_customer", table_name="segment_members",
    )
    op.drop_index(
        "ix_segment_members_segment", table_name="segment_members",
    )
    op.drop_table("segment_members")
    op.drop_index("ix_segments_org_type", table_name="segments")
    op.drop_table("segments")
    sa.Enum(name=SEGMENT_TYPE_ENUM_NAME).drop(op.get_bind(), checkfirst=True)
