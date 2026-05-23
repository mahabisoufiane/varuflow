"""Email campaign engine (Item 40, v55).

Pure + DB-bound split (same pattern as Items 30-39).

Pure layer
----------
* :func:`inject_gdpr_footer` — appends an unsubscribe footer so a
  single campaign template can never ship without one.
* :func:`sanitize_body_html` — strips ``<script>`` and ``javascript:``
  links. Rich-text editors still produce clean HTML most of the time,
  but a paste from a phishing email must never land in a customer
  inbox signed by us.
* :func:`sign_unsubscribe_token` / :func:`verify_unsubscribe_token` —
  HMAC-SHA256 signed ``campaign_id.customer_id`` pair. No DB round-trip
  to create one, and a forged link cannot flip another tenant's
  opt-out flag.
* :func:`compute_stats` — aggregates ``CampaignSend`` rows into
  ``{sent, failed, bounced, opened, open_rate, bounce_rate}``.

DB layer
--------
* :func:`build_recipient_list` — expands a segment into deduped
  ``(customer_id, email)`` tuples, excluding opted-out customers.
* :func:`send_campaign` — writes ``CampaignSend`` rows, dispatches
  via :func:`app.services.email.send_campaign_email`, flips status.
* :func:`process_due_campaigns` — scheduler entrypoint.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import html
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable


# ═══════════════════════════════════════════════════════════════════
# Footer + sanitisation (pure)
# ═══════════════════════════════════════════════════════════════════


# Stable sentinel — tests grep for it so a future refactor that
# accidentally drops the footer is caught before deploy.
GDPR_FOOTER_SENTINEL = "vf-campaign-footer"


def inject_gdpr_footer(
    body_html: str, *, unsubscribe_url: str, org_name: str,
) -> str:
    """Append a GDPR-compliant unsubscribe footer to a campaign body.

    Idempotent — if the sentinel is already present the body is
    returned unchanged, so a preview + final send cannot stack two
    footers.
    """
    if GDPR_FOOTER_SENTINEL in body_html:
        return body_html
    safe_org = html.escape(org_name or "")
    safe_url = html.escape(unsubscribe_url)
    footer = (
        f'\n<hr style="margin-top:32px;border:0;border-top:1px solid #e5e7eb"/>'
        f'<div class="{GDPR_FOOTER_SENTINEL}" '
        f'style="color:#888;font-size:12px;padding:12px 0;text-align:center">'
        f'You received this email from {safe_org}. '
        f'<a href="{safe_url}" style="color:#1a2332">Unsubscribe</a>'
        f' · Sent via Varuflow'
        f'</div>\n'
    )
    return body_html + footer


# Very small sanitiser — strips ``<script>…</script>`` and any
# ``javascript:`` / ``data:`` hrefs. We deliberately don't attempt a
# full HTML sanitiser (that would require a dependency); campaigns
# are owner-authored (paying customer), not untrusted UGC. The guard
# exists as belt-and-braces against a reckless paste.
_SCRIPT_RE = re.compile(r"<\s*script\b[^>]*>.*?</\s*script\s*>", re.IGNORECASE | re.DOTALL)
_EVIL_ATTR_RE = re.compile(
    r'(href|src)\s*=\s*["\'](?:javascript|data|vbscript):[^"\']*["\']',
    re.IGNORECASE,
)


def sanitize_body_html(body_html: str) -> str:
    body = _SCRIPT_RE.sub("", body_html or "")
    body = _EVIL_ATTR_RE.sub(r'\1="#"', body)
    return body


# ═══════════════════════════════════════════════════════════════════
# Unsubscribe tokens (pure)
# ═══════════════════════════════════════════════════════════════════


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _unb64(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def sign_unsubscribe_token(
    *, campaign_id: uuid.UUID, customer_id: uuid.UUID, secret: str,
) -> str:
    """Return a signed ``{campaign}.{customer}.{sig}`` token.

    Deterministic — the same (campaign, customer, secret) always
    produces the same token. No DB round-trip on generation, so we
    can mint thousands per campaign dispatch without load.
    """
    payload = f"{campaign_id}.{customer_id}".encode()
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).digest()
    return f"{campaign_id}.{customer_id}.{_b64(sig)}"


def verify_unsubscribe_token(
    token: str, *, secret: str,
) -> tuple[uuid.UUID, uuid.UUID] | None:
    """Return ``(campaign_id, customer_id)`` on success, None otherwise.

    A forged or tampered token is indistinguishable from noise; the
    caller maps ``None`` to 400 so a timing channel can't leak which
    campaign / customer pairs exist.
    """
    if not token or token.count(".") != 2:
        return None
    try:
        cid_s, cust_s, sig_s = token.split(".", 2)
        campaign_id = uuid.UUID(cid_s)
        customer_id = uuid.UUID(cust_s)
        expected = hmac.new(
            secret.encode(),
            f"{campaign_id}.{customer_id}".encode(),
            hashlib.sha256,
        ).digest()
        provided = _unb64(sig_s)
        if not hmac.compare_digest(expected, provided):
            return None
        return campaign_id, customer_id
    except Exception:  # noqa: BLE001 — any malformed input → None
        return None


# ═══════════════════════════════════════════════════════════════════
# Stats (pure)
# ═══════════════════════════════════════════════════════════════════


@dataclass
class CampaignStats:
    total: int
    sent: int
    failed: int
    bounced: int
    opened: int

    @property
    def open_rate(self) -> float:
        if self.sent <= 0:
            return 0.0
        return round(self.opened / self.sent, 4)

    @property
    def bounce_rate(self) -> float:
        if self.total <= 0:
            return 0.0
        return round(self.bounced / self.total, 4)

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "sent": self.sent,
            "failed": self.failed,
            "bounced": self.bounced,
            "opened": self.opened,
            "open_rate": self.open_rate,
            "bounce_rate": self.bounce_rate,
        }


def compute_stats(status_rows: Iterable[str]) -> CampaignStats:
    """Tally status strings into a :class:`CampaignStats`.

    Accepts a plain iterable of status strings so the pure layer can
    be exercised without importing the ORM. Unknown statuses count
    toward the total but no per-bucket counter, so a provider adding
    a new value doesn't under-count the ``total``.
    """
    total = 0
    sent = failed = bounced = opened = 0
    for s in status_rows:
        total += 1
        v = (s or "").upper()
        if v == "SENT":
            sent += 1
        elif v == "FAILED":
            failed += 1
        elif v == "BOUNCED":
            bounced += 1
        elif v == "OPENED":
            # Opens are a superset of sent — an opened email was sent.
            # Keep both counters so the UI can display "234 sent / 80 opened".
            opened += 1
            sent += 1
    return CampaignStats(
        total=total, sent=sent, failed=failed,
        bounced=bounced, opened=opened,
    )


# ═══════════════════════════════════════════════════════════════════
# DB layer
# ═══════════════════════════════════════════════════════════════════


async def build_recipient_list(
    db, *, segment_id: uuid.UUID, org_id: uuid.UUID,
) -> list[tuple[uuid.UUID, str]]:
    """Return ``(customer_id, email)`` tuples ready to receive a campaign.

    Filters out customers with no email and customers who have opted
    out. Enforces org ownership on the segment so a forged segment
    id can't leak another tenant's customers.
    """
    from sqlalchemy import select

    from app.models.invoicing import Customer
    from app.models.segments import Segment, SegmentMember

    rows = await db.execute(
        select(Customer.id, Customer.email)
        .join(SegmentMember, SegmentMember.customer_id == Customer.id)
        .join(Segment, Segment.id == SegmentMember.segment_id)
        .where(
            Segment.id == segment_id,
            Segment.org_id == org_id,
            Customer.email.is_not(None),
            Customer.email != "",
            Customer.email_opted_out == False,  # noqa: E712 — SQL boolean
        )
    )
    # Dedupe on email so an org that has the same email on two
    # customer rows (franchisee + HQ) still only gets one copy.
    seen: set[str] = set()
    out: list[tuple[uuid.UUID, str]] = []
    for cid, email in rows.all():
        if not email:
            continue
        key = email.lower().strip()
        if key in seen:
            continue
        seen.add(key)
        out.append((cid, email))
    return out


async def preview_campaign_html(
    db,
    *,
    campaign,
    unsubscribe_url: str,
    org_name: str,
) -> str:
    """Render the final HTML an average recipient would see."""
    body = sanitize_body_html(campaign.body_html or "")
    return inject_gdpr_footer(
        body, unsubscribe_url=unsubscribe_url, org_name=org_name,
    )


async def send_campaign(
    db,
    *,
    campaign,  # app.models.campaigns.Campaign
    org_name: str,
    base_unsubscribe_url: str,
    secret: str,
) -> int:
    """Dispatch a campaign to its full recipient list.

    Returns the number of recipients written. Safe to call twice — the
    unique ``(campaign_id, customer_id)`` constraint rejects duplicate
    rows, and the caller transitions the campaign to SENT after the
    first success.
    """
    from app.models.campaigns import CampaignSend, CampaignSendStatus, CampaignStatus
    from app.services.email import send_campaign_email

    if campaign.segment_id is None:
        raise ValueError("campaign_no_segment")

    recipients = await build_recipient_list(
        db, segment_id=campaign.segment_id, org_id=campaign.org_id,
    )

    for customer_id, email in recipients:
        token = sign_unsubscribe_token(
            campaign_id=campaign.id,
            customer_id=customer_id,
            secret=secret,
        )
        unsubscribe_url = f"{base_unsubscribe_url}?token={token}"
        rendered = inject_gdpr_footer(
            sanitize_body_html(campaign.body_html or ""),
            unsubscribe_url=unsubscribe_url,
            org_name=org_name,
        )
        try:
            ok = await send_campaign_email(
                to_email=email,
                subject=campaign.subject,
                body_html=rendered,
                org_name=org_name,
            )
            status = (
                CampaignSendStatus.SENT if ok
                else CampaignSendStatus.FAILED
            )
        except Exception:  # noqa: BLE001 — a provider error on one recipient
            # must not abort the rest of the send; record FAILED so
            # the operator can see what happened in the stats panel.
            status = CampaignSendStatus.FAILED

        db.add(CampaignSend(
            campaign_id=campaign.id,
            customer_id=customer_id,
            email=email,
            status=status,
        ))

    campaign.recipient_count = len(recipients)
    campaign.status = CampaignStatus.SENT
    campaign.sent_at = datetime.now(timezone.utc)
    await db.flush()
    return len(recipients)


async def mark_unsubscribed(db, *, customer_id: uuid.UUID) -> bool:
    """Flip ``customers.email_opted_out``. Returns True if a change
    happened. Idempotent — a second call on the same customer is a
    no-op and still returns False."""
    from app.models.invoicing import Customer

    cust = await db.get(Customer, customer_id)
    if cust is None:
        return False
    if cust.email_opted_out:
        return False
    cust.email_opted_out = True
    cust.email_opted_out_at = datetime.now(timezone.utc)
    await db.flush()
    return True


async def process_due_campaigns(db) -> list[uuid.UUID]:
    """Dispatch every SCHEDULED campaign whose ``scheduled_at <= now``.

    Returns the list of ids that completed this sweep. One commit per
    campaign so a single bad payload does not poison the whole queue.
    Called from :mod:`app.services.scheduler`.
    """
    from sqlalchemy import select

    from app.config import settings
    from app.models.campaigns import Campaign, CampaignStatus
    from app.models.organization import Organization

    now = datetime.now(timezone.utc)
    rows = await db.execute(
        select(Campaign).where(
            Campaign.status == CampaignStatus.SCHEDULED,
            Campaign.scheduled_at <= now,
        )
    )
    due = rows.scalars().all()
    sent_ids: list[uuid.UUID] = []
    for campaign in due:
        try:
            org = await db.get(Organization, campaign.org_id)
            org_name = getattr(org, "name", "") if org else ""
            await send_campaign(
                db,
                campaign=campaign,
                org_name=org_name,
                base_unsubscribe_url=f"{settings.FRONTEND_URL}/api/campaigns/unsubscribe",
                secret=settings.AUTH_JWT_SECRET,
            )
            await db.commit()
            sent_ids.append(campaign.id)
        except Exception:  # noqa: BLE001 — one bad campaign must not
            # block the others; log via the caller (scheduler has the
            # context + logger) and move on.
            await db.rollback()
    return sent_ids


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
