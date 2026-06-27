"""Tests for email campaign builder (Item 40, v55).

Pure + contract-style split (same as Items 28-39). The 3.9 sandbox
cannot import ``app.models.__init__`` (str | None annotations), so the
pure engine is exercised directly and DB/router invariants are locked
via source-text reading.

Required test names (spec):

* test_create_campaign_draft
* test_send_to_segment
* test_schedule_campaign
* test_track_send_status
* test_unsubscribe_removes_customer
* test_preview_email
* test_campaign_stats
* test_gdpr_footer_present
* test_org_isolation
* test_scheduler_sends_at_correct_time
"""
from __future__ import annotations

import pathlib
import uuid

import pytest

from app.services import campaign_engine as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1] / "app"


def _read(relpath: str) -> str:
    return (_BACKEND_ROOT / relpath).read_text()


ROUTER_SRC = _read("routers/campaigns.py")
SERVICE_SRC = _read("services/campaign_engine.py")
SCHEDULER_SRC = _read("services/scheduler.py")
MODEL_SRC = _read("models/campaigns.py")
EMAIL_SRC = _read("services/email.py")
MAIN_SRC = _read("main.py")
MIGRATION_SRC = (
    _BACKEND_ROOT.parent
    / "migrations"
    / "versions"
    / "b1c2d3e4f5a6_v55_campaigns.py"
).read_text()
INVOICING_SRC = _read("models/invoicing.py")


SECRET = "test-secret-do-not-use-in-production"


# ═══════════════════════════════════════════════════════════════════
# 1. test_create_campaign_draft
# ═══════════════════════════════════════════════════════════════════


def test_create_campaign_draft():
    # Router POST / creates a DRAFT campaign with audit logging.
    assert "class CampaignCreateIn" in ROUTER_SRC
    assert "status=CampaignStatus.DRAFT" in ROUTER_SRC
    assert 'action="campaign.created"' in ROUTER_SRC

    # Model default is DRAFT so a forgotten status arg can't escape it.
    assert "default=CampaignStatus.DRAFT" in MODEL_SRC

    # Migration enum carries all three values.
    assert '"DRAFT", "SCHEDULED", "SENT"' in MIGRATION_SRC

    # Segment FK enforced on create.
    assert 'detail="segment_not_found"' in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 2. test_send_to_segment
# ═══════════════════════════════════════════════════════════════════


def test_send_to_segment():
    # Engine walks the segment's membership into CampaignSend rows.
    assert "async def send_campaign" in SERVICE_SRC
    assert "build_recipient_list" in SERVICE_SRC
    # Opted-out customers are excluded at the recipient-build layer.
    assert "email_opted_out == False" in SERVICE_SRC
    # Router exposes the ``send now`` endpoint and audits it.
    assert 'action="campaign.sent"' in ROUTER_SRC
    # Must have a segment to send.
    assert 'detail="campaign_no_segment"' in ROUTER_SRC

    # Email service has a campaign-specific helper — kept thin so
    # the engine owns the HTML shape.
    assert "async def send_campaign_email" in EMAIL_SRC
    assert 'campaigns@varuflow.app' in EMAIL_SRC


# ═══════════════════════════════════════════════════════════════════
# 3. test_schedule_campaign
# ═══════════════════════════════════════════════════════════════════


def test_schedule_campaign():
    # Router exposes /schedule and transitions to SCHEDULED.
    assert "def schedule_campaign" in ROUTER_SRC
    assert "CampaignStatus.SCHEDULED" in ROUTER_SRC
    # Past dates are rejected — a timezone swap must not trigger an
    # instant send without the explicit /send endpoint.
    assert 'detail="scheduled_at_in_past"' in ROUTER_SRC
    # Audit action present.
    assert 'action="campaign.scheduled"' in ROUTER_SRC
    # Migration has a partial index on SCHEDULED rows so the dispatch
    # sweep is cheap even with thousands of sent campaigns.
    assert "ix_campaigns_scheduled" in MIGRATION_SRC
    assert "status = 'SCHEDULED'" in MIGRATION_SRC


# ═══════════════════════════════════════════════════════════════════
# 4. test_track_send_status
# ═══════════════════════════════════════════════════════════════════


def test_track_send_status():
    # Status enum covers all four states — sent, failed, bounced, opened.
    assert "SENT" in MODEL_SRC
    assert "FAILED" in MODEL_SRC
    assert "BOUNCED" in MODEL_SRC
    assert "OPENED" in MODEL_SRC
    assert '"SENT", "FAILED", "BOUNCED", "OPENED"' in MIGRATION_SRC

    # Engine records FAILED on transport error rather than aborting
    # the whole campaign.
    assert "CampaignSendStatus.FAILED" in SERVICE_SRC

    # Unique (campaign_id, customer_id) guards against double-inserts.
    assert "uq_campaign_sends_campaign_customer" in MIGRATION_SRC
    assert "uq_campaign_sends_campaign_customer" in MODEL_SRC


# ═══════════════════════════════════════════════════════════════════
# 5. test_unsubscribe_removes_customer
# ═══════════════════════════════════════════════════════════════════


def test_unsubscribe_removes_customer():
    # Public /unsubscribe verifies an HMAC-signed token.
    assert 'svc.verify_unsubscribe_token' in ROUTER_SRC
    assert 'detail="invalid_token"' in ROUTER_SRC
    # Flipping the flag audits as "campaign.unsubscribed".
    assert 'action="campaign.unsubscribed"' in ROUTER_SRC

    # Engine exposes the flag-mutation helper.
    assert "async def mark_unsubscribed" in SERVICE_SRC
    assert "email_opted_out = True" in SERVICE_SRC

    # Model has the column + migration adds it.
    assert "email_opted_out" in INVOICING_SRC
    assert '"email_opted_out"' in MIGRATION_SRC
    assert '"email_opted_out_at"' in MIGRATION_SRC

    # Unsubscribed customers are filtered out on the next send.
    assert "Customer.email_opted_out == False" in SERVICE_SRC

    # Tokens round-trip under the engine helpers.
    cid = uuid.uuid4()
    uid = uuid.uuid4()
    token = svc.sign_unsubscribe_token(
        campaign_id=cid, customer_id=uid, secret=SECRET,
    )
    parsed = svc.verify_unsubscribe_token(token, secret=SECRET)
    assert parsed == (cid, uid)
    # A tampered signature fails.
    assert svc.verify_unsubscribe_token(token + "x", secret=SECRET) is None
    # A different secret fails.
    assert svc.verify_unsubscribe_token(token, secret="wrong") is None
    # Malformed inputs fail safely.
    assert svc.verify_unsubscribe_token("", secret=SECRET) is None
    assert svc.verify_unsubscribe_token("a.b", secret=SECRET) is None
    assert svc.verify_unsubscribe_token("not-a-uuid.nope.xxx", secret=SECRET) is None


# ═══════════════════════════════════════════════════════════════════
# 6. test_preview_email
# ═══════════════════════════════════════════════════════════════════


def test_preview_email():
    # Router /preview renders the full body + audits.
    assert "def preview_campaign" in ROUTER_SRC
    assert 'action="campaign.previewed"' in ROUTER_SRC
    # Preview subject is prefixed to avoid confusion with the real send.
    assert '[PREVIEW]' in ROUTER_SRC

    # Engine's sanitiser strips <script> and javascript: links.
    dirty = '<p>Hi</p><script>alert(1)</script><a href="javascript:evil()">x</a>'
    clean = svc.sanitize_body_html(dirty)
    assert "<script" not in clean.lower()
    assert "javascript:" not in clean.lower()

    # Preview output still carries the GDPR footer.
    rendered = svc.inject_gdpr_footer(
        clean, unsubscribe_url="https://x.example/u?token=abc", org_name="Acme",
    )
    assert svc.GDPR_FOOTER_SENTINEL in rendered
    # HTML escaping on org/url parts — a name with "<" must not break
    # the rendered preview.
    rendered2 = svc.inject_gdpr_footer(
        "<p>hi</p>", unsubscribe_url="https://x/?q=1&a=2", org_name="A<b>Co",
    )
    assert "A&lt;b&gt;Co" in rendered2
    # Ampersand in URL is HTML-escaped inside the href.
    assert "&amp;a=2" in rendered2


# ═══════════════════════════════════════════════════════════════════
# 7. test_campaign_stats
# ═══════════════════════════════════════════════════════════════════


def test_campaign_stats():
    # Pure stats aggregator.
    stats = svc.compute_stats(
        ["SENT", "SENT", "FAILED", "BOUNCED", "OPENED", "OPENED"]
    )
    # opened counts also count as sent (they were necessarily delivered).
    assert stats.total == 6
    assert stats.sent == 4  # 2 SENT + 2 OPENED
    assert stats.failed == 1
    assert stats.bounced == 1
    assert stats.opened == 2
    # Open rate is opened / sent.
    assert stats.open_rate == pytest.approx(2 / 4, rel=1e-3)
    # Bounce rate is bounced / total.
    assert stats.bounce_rate == pytest.approx(1 / 6, abs=1e-3)

    # Zero input produces zero rates (no div-by-zero).
    empty = svc.compute_stats([])
    assert empty.total == 0
    assert empty.open_rate == 0.0
    assert empty.bounce_rate == 0.0

    # Unknown statuses count toward total but nothing else.
    unknown = svc.compute_stats(["QUEUED", "UNKNOWN"])
    assert unknown.total == 2
    assert unknown.sent == 0
    assert unknown.bounced == 0

    # Router /stats + /sends endpoints wired.
    assert "def campaign_stats" in ROUTER_SRC
    assert "def list_sends" in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 8. test_gdpr_footer_present
# ═══════════════════════════════════════════════════════════════════


def test_gdpr_footer_present():
    # Sentinel is the CSS class; a refactor that drops it surfaces
    # immediately in the test.
    assert svc.GDPR_FOOTER_SENTINEL

    rendered = svc.inject_gdpr_footer(
        "<p>Hello</p>",
        unsubscribe_url="https://varuflow.app/api/campaigns/unsubscribe?token=xyz",
        org_name="Acme AB",
    )
    assert svc.GDPR_FOOTER_SENTINEL in rendered
    assert "Unsubscribe" in rendered
    assert "https://varuflow.app/api/campaigns/unsubscribe?token=xyz" in rendered
    assert "Acme AB" in rendered

    # Idempotent — running twice does not stack two footers.
    twice = svc.inject_gdpr_footer(
        rendered,
        unsubscribe_url="https://varuflow.app/api/campaigns/unsubscribe?token=xyz",
        org_name="Acme AB",
    )
    assert twice.count(svc.GDPR_FOOTER_SENTINEL) == 1

    # The engine's send path always goes through inject_gdpr_footer.
    assert "inject_gdpr_footer(" in SERVICE_SRC
    # Router's preview + send both call into it (preview directly,
    # send indirectly via svc.send_campaign).
    assert "svc.inject_gdpr_footer" in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 9. test_org_isolation
# ═══════════════════════════════════════════════════════════════════


def test_org_isolation():
    # Router _load guards campaign by (id, org_id) — 404 otherwise.
    assert "Campaign.org_id == org_id" in ROUTER_SRC
    assert 'detail="campaign_not_found"' in ROUTER_SRC
    # Segment resolution also filters by org on create + update.
    assert "Segment.org_id == org_id" in ROUTER_SRC

    # Engine build_recipient_list enforces Segment.org_id on the join.
    assert "Segment.org_id == org_id" in SERVICE_SRC

    # Migration enforces CASCADE on org deletion so orphan campaigns
    # can't linger after a tenant purge.
    assert 'ForeignKey("organizations.id", ondelete="CASCADE")' in MIGRATION_SRC
    # Customer CASCADE so a deleted customer drops out of every
    # send ledger automatically.
    assert 'ForeignKey("customers.id", ondelete="CASCADE")' in MIGRATION_SRC
    # Segment SET NULL so deleting a segment does not wipe campaign
    # history.
    assert 'ForeignKey("segments.id", ondelete="SET NULL")' in MIGRATION_SRC


# ═══════════════════════════════════════════════════════════════════
# 10. test_scheduler_sends_at_correct_time
# ═══════════════════════════════════════════════════════════════════


def test_scheduler_sends_at_correct_time():
    # Scheduler wires a dispatch job with its own advisory lock.
    assert "_LOCK_CAMPAIGN_DISPATCH" in SCHEDULER_SRC
    assert "_campaign_dispatch_sweep" in SCHEDULER_SRC
    assert 'id="campaign_dispatch"' in SCHEDULER_SRC
    # 5-min interval so a campaign scheduled for 09:00 arrives within
    # 09:00–09:05 wall-clock.
    assert "IntervalTrigger(minutes=5)" in SCHEDULER_SRC

    # Engine picks only due rows — scheduled_at <= now AND SCHEDULED.
    assert "Campaign.status == CampaignStatus.SCHEDULED" in SERVICE_SRC
    assert "Campaign.scheduled_at <= now" in SERVICE_SRC
    # Post-dispatch transitions to SENT with sent_at stamped.
    assert "campaign.status = CampaignStatus.SENT" in SERVICE_SRC
    assert "campaign.sent_at = datetime.now(timezone.utc)" in SERVICE_SRC


# ═══════════════════════════════════════════════════════════════════
# Additional invariants
# ═══════════════════════════════════════════════════════════════════


def test_migration_v55_shape():
    assert 'revision = "b1c2d3e4f5a6"' in MIGRATION_SRC
    assert 'down_revision = "f1a2b3c4d5e6"' in MIGRATION_SRC
    assert 'op.create_table(\n        "campaigns"' in MIGRATION_SRC
    assert 'op.create_table(\n        "campaign_sends"' in MIGRATION_SRC
    # Both enum types named + dropped on downgrade.
    assert 'CAMPAIGN_STATUS_ENUM_NAME = "campaign_status"' in MIGRATION_SRC
    assert 'CAMPAIGN_SEND_STATUS_ENUM_NAME = "campaign_send_status"' in MIGRATION_SRC
    # Customer table widens with the opt-out columns.
    assert 'op.add_column(\n        "customers",' in MIGRATION_SRC


def test_sanitizer_survives_common_html():
    # Bold / em / paragraph markup passes through unchanged.
    body = '<p>Hi <strong>there</strong></p><p>Thanks, <em>Acme</em></p>'
    assert svc.sanitize_body_html(body) == body
    # data: URLs on images are treated as evil too.
    evil_img = '<img src="data:image/png;base64,AAAA"/>'
    assert 'data:' not in svc.sanitize_body_html(evil_img).lower()


def test_compute_stats_open_rate_no_sends():
    stats = svc.compute_stats(["FAILED", "FAILED"])
    # No sent / opened → open_rate 0 (not NaN).
    assert stats.open_rate == 0.0
    assert stats.bounce_rate == 0.0


def test_router_registered_in_main():
    assert "campaigns.router" in MAIN_SRC
    # Import line includes ``campaigns``.
    assert "campaigns," in MAIN_SRC
