"""Add 14-day PRO trial columns to organizations.

Revision ID: qq7rr8ss9tt0
Revises:     z3t4u5v6w7x8
Create Date: 2026-05-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "qq7rr8ss9tt0"
down_revision = "z3t4u5v6w7x8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("trial_plan", sa.String(20), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("trial_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("trial_converted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "trial_extended_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "organizations",
        sa.Column("trial_source", sa.String(50), nullable=True),
    )

    op.create_index(
        "ix_organizations_trial_ends_at",
        "organizations",
        ["trial_ends_at"],
        postgresql_where=sa.text("trial_ends_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_organizations_trial_ends_at",
        table_name="organizations",
    )
    op.drop_column("organizations", "trial_source")
    op.drop_column("organizations", "trial_extended_count")
    op.drop_column("organizations", "trial_converted_at")
    op.drop_column("organizations", "trial_ends_at")
    op.drop_column("organizations", "trial_started_at")
    op.drop_column("organizations", "trial_plan")
