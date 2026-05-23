"""Local payment methods - Klarna, Swish, Vipps, Tabby, mada, KNET

Revision ID: aa1bb2cc3dd4
Revises: xx4yy5zz6aa7
Create Date: 2026-05-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "aa1bb2cc3dd4"
down_revision = "xx4yy5zz6aa7"
branch_labels = None
depends_on = None


def upgrade():
    # local_payment_configs — per-org config for each payment provider
    op.create_table(
        "local_payment_configs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("api_key_encrypted", sa.Text, nullable=True),
        sa.Column("api_secret_encrypted", sa.Text, nullable=True),
        sa.Column("merchant_id", sa.String(200), nullable=True),
        sa.Column("webhook_secret_encrypted", sa.Text, nullable=True),
        sa.Column("config_json", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("org_id", "provider", name="uq_local_payment_config"),
    )
    op.create_index(
        "ix_local_payment_configs_org_id", "local_payment_configs", ["org_id"]
    )

    # local_payment_sessions — each payment attempt
    op.create_table(
        "local_payment_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "invoice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoices.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "currency", sa.String(3), nullable=False, server_default="SEK"
        ),
        sa.Column("customer_email", sa.String(320), nullable=True),
        sa.Column("customer_name", sa.String(200), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("provider_session_id", sa.String(200), nullable=True),
        sa.Column("redirect_url", sa.Text, nullable=True),
        sa.Column("callback_url", sa.Text, nullable=True),
        sa.Column("provider_response", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_local_payment_sessions_org_id", "local_payment_sessions", ["org_id"]
    )
    op.create_index(
        "ix_local_payment_sessions_invoice_id",
        "local_payment_sessions",
        ["invoice_id"],
    )
    op.create_index(
        "ix_local_payment_sessions_provider_session_id",
        "local_payment_sessions",
        ["provider_session_id"],
    )


def downgrade():
    op.drop_table("local_payment_sessions")
    op.drop_table("local_payment_configs")
