"""v68 — Custom fields for products, customers and invoices (Item 59).

Operators need to attach tenant-specific metadata to the core
business entities without waiting for a migration per request. Two
tables:

* ``custom_field_definitions`` — per-org schema: name, label, type,
  required flag, option list, and which ``entity_type`` the field
  attaches to. Unique ``(org_id, entity_type, name)`` so a lookup is
  cheap and names can't collide within the same entity scope.
* ``custom_field_values`` — per-row payload: one row per
  ``(entity_type, entity_id, definition_id)``. Stores the raw string
  value; the service casts on read based on ``definition.type``.

Supported types (validated at the service layer):
``text``, ``number``, ``boolean``, ``date``, ``select``.

Revision: d8f0b2c4e6a9
Revises:  c7e9a1b3d5f8 (v67 — checkin tokens, Item 58)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "d8f0b2c4e6a9"
down_revision = "c7e9a1b3d5f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "custom_field_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # entity_type ∈ {product, customer, invoice}
        sa.Column("entity_type", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=False),
        # type ∈ {text, number, boolean, date, select}
        sa.Column("field_type", sa.String(length=16), nullable=False),
        sa.Column(
            "is_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        # For field_type=select: JSON list of allowed string values.
        sa.Column(
            "options",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "display_order",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "org_id",
            "entity_type",
            "name",
            name="uq_custom_fields_org_entity_name",
        ),
    )
    op.create_index(
        "ix_custom_field_defs_org_entity",
        "custom_field_definitions",
        ["org_id", "entity_type"],
    )

    op.create_table(
        "custom_field_values",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "definition_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "custom_field_definitions.id", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(length=16), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "definition_id",
            "entity_id",
            name="uq_custom_field_values_definition_entity",
        ),
    )
    op.create_index(
        "ix_custom_field_values_entity",
        "custom_field_values",
        ["entity_type", "entity_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_custom_field_values_entity", table_name="custom_field_values"
    )
    op.drop_table("custom_field_values")
    op.drop_index(
        "ix_custom_field_defs_org_entity",
        table_name="custom_field_definitions",
    )
    op.drop_table("custom_field_definitions")
