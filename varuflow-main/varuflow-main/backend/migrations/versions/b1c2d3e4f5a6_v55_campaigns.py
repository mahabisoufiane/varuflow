"""v55 — email campaign builder (Item 40).

Adds three structural pieces so orgs can build + dispatch targeted
email campaigns to a customer segment:

* ``campaigns`` — one row per campaign. Carries the draft, schedule
  and summary stats. ``segment_id`` is nullable so a deleted segment
  does not cascade-delete the campaign history (audit requirement).
* ``campaign_sends`` — one row per recipient per campaign. Records
  deliverability (``sent``, ``failed``, ``bounced``, ``opened``) so
  the stats endpoint can compute open / bounce rates without
  replaying the outbound queue.
* ``customers.email_opted_out`` / ``email_opted_out_at`` columns —
  the GDPR unsubscribe flag the /unsubscribe endpoint flips. Kept on
  the customer row (not a side-table) so every email sender can test
  the flag with a single column read.

Spec asked for v47; v47 is taken by ``e8f0a2b4c6d9_v47_bookings.py``.
Landed at v55 — the next free slot after v54 (segments, Item 39).
Same shift rationale as §58–§68.

Revision: b1c2d3e4f5a6
Revises:  f1a2b3c4d5e6 (v54 — customer segmentation, Item 39)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b1c2d3e4f5a6"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


CAMPAIGN_STATUS_ENUM_NAME = "campaign_status"
CAMPAIGN_SEND_STATUS_ENUM_NAME = "campaign_send_status"


def upgrade() -> None:
    campaign_status = postgresql.ENUM(
        "DRAFT", "SCHEDULED", "SENT",
        name=CAMPAIGN_STATUS_ENUM_NAME,
    )
    campaign_status.create(op.get_bind(), checkfirst=True)

    send_status = postgresql.ENUM(
        "SENT", "FAILED", "BOUNCED", "OPENED",
        name=CAMPAIGN_SEND_STATUS_ENUM_NAME,
    )
    send_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("subject", sa.String(length=300), nullable=False),
        # Rich-text body as HTML. Always passed through the sanitiser
        # at send time; stored as authored so the editor round-trips.
        sa.Column("body_html", sa.Text, nullable=False),
        # Nullable so a segment deletion doesn't break the send ledger.
        # ON DELETE SET NULL keeps the campaign history even if the
        # targeted segment is later removed.
        sa.Column(
            "segment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("segments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                name=CAMPAIGN_STATUS_ENUM_NAME, create_type=False,
            ),
            nullable=False,
            server_default="DRAFT",
        ),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "recipient_count",
            sa.Integer, nullable=False, server_default="0",
        ),
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
    )
    op.create_index(
        "ix_campaigns_org_status",
        "campaigns",
        ["org_id", "status"],
    )
    # Scheduler dispatch sweep selects rows by (status, scheduled_at).
    # Partial index keeps the working set tiny — only pending rows are
    # ever scanned, so a tenant with thousands of sent campaigns does
    # not slow the nightly sweep.
    op.create_index(
        "ix_campaigns_scheduled",
        "campaigns",
        ["scheduled_at"],
        postgresql_where=sa.text("status = 'SCHEDULED'"),
    )

    op.create_table(
        "campaign_sends",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Email is denormalised onto the send row so a later email
        # rotation on the customer record doesn't falsify historical
        # delivery logs (regulatory requirement under GDPR Art. 30).
        sa.Column("email", sa.String(length=512), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                name=CAMPAIGN_SEND_STATUS_ENUM_NAME, create_type=False,
            ),
            nullable=False,
            server_default="SENT",
        ),
        sa.Column(
            "sent_at",
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
        # A customer must appear at most once per campaign — protects
        # against a resend race inserting twice for the same recipient.
        sa.UniqueConstraint(
            "campaign_id", "customer_id",
            name="uq_campaign_sends_campaign_customer",
        ),
    )
    op.create_index(
        "ix_campaign_sends_campaign",
        "campaign_sends",
        ["campaign_id"],
    )
    op.create_index(
        "ix_campaign_sends_status",
        "campaign_sends",
        ["campaign_id", "status"],
    )

    # Unsubscribe flag on customers. Everything that emails a customer
    # marketing content MUST consult this column; transactional emails
    # (invoices, dunning) are exempt because those are lawful-basis
    # "contract performance" and not covered by the opt-out.
    op.add_column(
        "customers",
        sa.Column(
            "email_opted_out",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "customers",
        sa.Column("email_opted_out_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("customers", "email_opted_out_at")
    op.drop_column("customers", "email_opted_out")

    op.drop_index("ix_campaign_sends_status", table_name="campaign_sends")
    op.drop_index("ix_campaign_sends_campaign", table_name="campaign_sends")
    op.drop_table("campaign_sends")

    op.drop_index("ix_campaigns_scheduled", table_name="campaigns")
    op.drop_index("ix_campaigns_org_status", table_name="campaigns")
    op.drop_table("campaigns")

    sa.Enum(name=CAMPAIGN_SEND_STATUS_ENUM_NAME).drop(op.get_bind(), checkfirst=True)
    sa.Enum(name=CAMPAIGN_STATUS_ENUM_NAME).drop(op.get_bind(), checkfirst=True)
