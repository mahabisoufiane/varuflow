"""Investor Board Communication and Marketing Insights tables.

Revision ID: dd3ee4ff5gg6
Revises:     cc3dd4ee5ff6
Create Date: 2026-05-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "dd3ee4ff5gg6"
down_revision = "cc3dd4ee5ff6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── investor_updates ────────────────────────────────────────────────────────
    op.create_table(
        "investor_updates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("period_month", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("revenue_snapshot", sa.Numeric(18, 2), nullable=True),
        sa.Column("burn_rate", sa.Numeric(18, 2), nullable=True),
        sa.Column("runway_months", sa.Numeric(6, 1), nullable=True),
        sa.Column("key_wins", sa.Text(), nullable=True),
        sa.Column("challenges", sa.Text(), nullable=True),
        sa.Column("next_milestones", sa.Text(), nullable=True),
        sa.Column("generated_pdf_url", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_investor_updates_org_id", "investor_updates", ["org_id"])

    op.create_table(
        "investor_update_recipients",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("update_id", UUID(as_uuid=True),
                  sa.ForeignKey("investor_updates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_investor_update_recipients_update_id", "investor_update_recipients", ["update_id"])

    # ── cap_table ───────────────────────────────────────────────────────────────
    op.create_table(
        "shareholders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("shareholder_type", sa.String(30), nullable=False, server_default="other"),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_shareholders_org_id", "shareholders", ["org_id"])

    op.create_table(
        "share_classes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("authorized_shares", sa.BigInteger(), nullable=True),
        sa.Column("liquidation_priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("has_anti_dilution", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("has_voting_rights", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_share_classes_org_id", "share_classes", ["org_id"])

    op.create_table(
        "shareholdings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shareholder_id", UUID(as_uuid=True),
                  sa.ForeignKey("shareholders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("share_class_id", UUID(as_uuid=True),
                  sa.ForeignKey("share_classes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shares", sa.BigInteger(), nullable=False),
        sa.Column("price_paid", sa.Numeric(14, 6), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="SEK"),
        sa.Column("grant_date", sa.Date(), nullable=True),
        sa.Column("vesting_start", sa.Date(), nullable=True),
        sa.Column("vesting_months", sa.Integer(), nullable=True),
        sa.Column("cliff_months", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_shareholdings_org_id", "shareholdings", ["org_id"])
    op.create_index("ix_shareholdings_shareholder_id", "shareholdings", ["shareholder_id"])

    op.create_table(
        "dilution_scenarios",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("new_shares", sa.BigInteger(), nullable=False),
        sa.Column("pre_money_valuation", sa.Numeric(18, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="SEK"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_dilution_scenarios_org_id", "dilution_scenarios", ["org_id"])

    # ── board_packs ─────────────────────────────────────────────────────────────
    op.create_table(
        "board_packs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("meeting_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("financial_period", sa.String(50), nullable=True),
        sa.Column("agenda", sa.Text(), nullable=True),
        sa.Column("executive_summary", sa.Text(), nullable=True),
        sa.Column("kpi_snapshot", JSONB(), nullable=True),
        sa.Column("pdf_url", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_board_packs_org_id", "board_packs", ["org_id"])
    op.create_index("ix_board_packs_meeting_date", "board_packs", ["meeting_date"])

    # ── data_room ───────────────────────────────────────────────────────────────
    op.create_table(
        "data_room_folders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("parent_folder_id", UUID(as_uuid=True),
                  sa.ForeignKey("data_room_folders.id", ondelete="CASCADE"), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_data_room_folders_org_id", "data_room_folders", ["org_id"])

    op.create_table(
        "data_room_documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("folder_id", UUID(as_uuid=True),
                  sa.ForeignKey("data_room_folders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("file_url", sa.Text(), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("uploaded_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_data_room_documents_org_id", "data_room_documents", ["org_id"])
    op.create_index("ix_data_room_documents_folder_id", "data_room_documents", ["folder_id"])

    op.create_table(
        "data_room_shares",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("token", sa.String(64), nullable=False, unique=True),
        sa.Column("folder_ids", JSONB(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_data_room_shares_org_id", "data_room_shares", ["org_id"])
    op.create_index("ix_data_room_shares_token", "data_room_shares", ["token"], unique=True)

    # ── marketing_attribution ───────────────────────────────────────────────────
    op.create_table(
        "attribution_sources",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("channel", sa.String(50), nullable=False, server_default="other"),
        sa.Column("utm_source", sa.String(200), nullable=True),
        sa.Column("utm_medium", sa.String(200), nullable=True),
        sa.Column("utm_campaign", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_attribution_sources_org_id", "attribution_sources", ["org_id"])

    op.create_table(
        "attribution_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=True),
        sa.Column("source_id", UUID(as_uuid=True),
                  sa.ForeignKey("attribution_sources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("channel", sa.String(50), nullable=True),
        sa.Column("revenue", sa.Numeric(18, 2), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_attribution_events_org_id", "attribution_events", ["org_id"])
    op.create_index("ix_attribution_events_source_id", "attribution_events", ["source_id"])
    op.create_index("ix_attribution_events_occurred_at", "attribution_events", ["occurred_at"])

    # ── ab_tests ─────────────────────────────────────────────────────────────────
    op.create_table(
        "ab_tests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("campaign_id", UUID(as_uuid=True), nullable=True),
        sa.Column("test_metric", sa.String(30), nullable=False, server_default="open_rate"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("winner_variant", sa.String(1), nullable=True),
        sa.Column("auto_promote", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_ab_tests_org_id", "ab_tests", ["org_id"])

    op.create_table(
        "ab_test_variants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("ab_test_id", UUID(as_uuid=True),
                  sa.ForeignKey("ab_tests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("variant", sa.String(1), nullable=False),
        sa.Column("subject_line", sa.String(300), nullable=True),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("recipient_pct", sa.Numeric(5, 2), nullable=False, server_default="50"),
        sa.Column("sent_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("open_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("click_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("conversion_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_ab_test_variants_test_id", "ab_test_variants", ["ab_test_id"])

    # ── landing_pages ────────────────────────────────────────────────────────────
    op.create_table(
        "landing_pages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("headline", sa.String(300), nullable=True),
        sa.Column("subheadline", sa.Text(), nullable=True),
        sa.Column("cta_text", sa.String(100), nullable=True),
        sa.Column("cta_url", sa.String(500), nullable=True),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("lead_form_id", UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("org_id", "slug", name="uq_landing_pages_org_slug"),
    )
    op.create_index("ix_landing_pages_org_id", "landing_pages", ["org_id"])

    # ── marketing_broadcasts ─────────────────────────────────────────────────────
    op.create_table(
        "marketing_broadcasts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False, server_default="sms"),
        sa.Column("segment_id", UUID(as_uuid=True), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recipient_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("delivered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("opt_out_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_marketing_broadcasts_org_id", "marketing_broadcasts", ["org_id"])

    # ── nps_surveys ──────────────────────────────────────────────────────────────
    op.create_table(
        "nps_surveys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("question", sa.Text(), nullable=False,
                  server_default="How likely are you to recommend us to a friend or colleague?"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("response_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_score", sa.Numeric(4, 2), nullable=True),
        sa.Column("promoter_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("passive_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("detractor_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_nps_surveys_org_id", "nps_surveys", ["org_id"])

    op.create_table(
        "nps_responses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("survey_id", UUID(as_uuid=True),
                  sa.ForeignKey("nps_surveys.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=True),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("respondent_email", sa.String(320), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_nps_responses_survey_id", "nps_responses", ["survey_id"])
    op.create_index("ix_nps_responses_org_id", "nps_responses", ["org_id"])


def downgrade() -> None:
    op.drop_table("nps_responses")
    op.drop_table("nps_surveys")
    op.drop_table("marketing_broadcasts")
    op.drop_table("landing_pages")
    op.drop_table("ab_test_variants")
    op.drop_table("ab_tests")
    op.drop_table("attribution_events")
    op.drop_table("attribution_sources")
    op.drop_table("data_room_shares")
    op.drop_table("data_room_documents")
    op.drop_table("data_room_folders")
    op.drop_table("dilution_scenarios")
    op.drop_table("shareholdings")
    op.drop_table("share_classes")
    op.drop_table("shareholders")
    op.drop_table("board_packs")
    op.drop_table("investor_update_recipients")
    op.drop_table("investor_updates")
