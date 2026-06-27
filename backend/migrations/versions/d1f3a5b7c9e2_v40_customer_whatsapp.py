"""v40: customer WhatsApp number (Item 18)

Revision ID: d1f3a5b7c9e2
Revises: c7e9a2b4d6f1
Create Date: 2026-04-23

Adds the opt-in WhatsApp contact number used by the extended dunning
ladder (stage 2+ delivers a WhatsApp reminder in addition to email when
a number is present). Kept optional so existing customers stay on
email-only dunning until the merchant fills it in — the v39 → v40
upgrade is behaviour-preserving.

``whatsapp_number`` is stored as a raw ``String(50)`` mirroring
``phone``. Normalisation to E.164 (+46…) happens at the service-layer
boundary in ``app.services.whatsapp`` so we never reject a paste from a
merchant UI; the service rejects unparseable values and the sweep
falls back to email-only.
"""
from alembic import op
import sqlalchemy as sa


revision = "d1f3a5b7c9e2"
down_revision = "c7e9a2b4d6f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "customers",
        sa.Column("whatsapp_number", sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("customers", "whatsapp_number")
