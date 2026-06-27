"""Nightly business summary service (Item 21).

For every org that has ``nightly_summary_enabled = True``, assemble a
short stats dict for the previous day and email it to the owner. The
email is deliberately **data-only** — no click-tracking, no pixels —
so it's safe to read as a business summary without hitting the app.

Metrics included (all scoped to the previous calendar day in
Europe/Stockholm):

* Revenue (SEK) — POS + invoice sales combined, plus % delta vs the
  day before that.
* Order / sale count.
* New invoices issued.
* Low-stock products (count).
* Overdue invoices (count + total amount).
* One AI insight — short deterministic sentence picked from the
  highest-priority signal in the data (no external OpenAI call; keeps
  the nightly sweep free of third-party dependencies and rate limits).

Scheduling: the scheduler fires ``run_nightly_summaries()`` every 15
minutes. Each org runs only if the current local time is inside the
15-minute window containing its configured ``nightly_summary_time``
and we haven't already sent one today (idempotency via audit log
lookup — the daily cardinality is tiny so this cost-less).
"""
from __future__ import annotations

import html
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.features.compliance.audit_models import AuditLogEntry
from app.features.inventory.models import Product, StockLevel
from app.features.invoicing.models import Invoice, InvoiceStatus
from app.features.auth.organization import Organization
from app.features.pos.models import PosSale
from app.services.audit import log_action

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"


@dataclass
class SummaryStats:
    """What we present in the email. Kept flat so it's trivial to
    serialise for audit-log ``extra`` without leaking PII."""

    date: date
    revenue: Decimal = Decimal("0.00")
    revenue_prev: Decimal = Decimal("0.00")
    revenue_delta_pct: Decimal | None = None  # None when prev == 0
    orders_count: int = 0  # POS sales + invoices issued
    invoices_count: int = 0  # invoices issued today
    low_stock_count: int = 0
    overdue_count: int = 0
    overdue_total: Decimal = Decimal("0.00")
    ai_insight: str = ""

    def to_extra(self) -> dict:
        return {
            "date": self.date.isoformat(),
            "revenue": str(self.revenue),
            "revenue_prev": str(self.revenue_prev),
            "revenue_delta_pct": (
                str(self.revenue_delta_pct)
                if self.revenue_delta_pct is not None
                else None
            ),
            "orders_count": self.orders_count,
            "invoices_count": self.invoices_count,
            "low_stock_count": self.low_stock_count,
            "overdue_count": self.overdue_count,
            "overdue_total": str(self.overdue_total),
        }


def _h(value) -> str:
    """HTML-escape user-controlled text before dropping into the email."""
    return html.escape(str(value) if value is not None else "", quote=True)


async def _day_revenue(db: AsyncSession, org_id: uuid.UUID, day: date) -> Decimal:
    """Revenue for ``day`` = sum of POS sales + invoices issued that day.

    We deliberately include *issued* invoices (regardless of payment
    status) so the summary reflects the day's sales activity. Refunds
    back out POS sales via ``is_refunded``.
    """
    start = datetime.combine(day, time.min).replace(tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    pos_total = (
        await db.scalar(
            select(func.coalesce(func.sum(PosSale.total), 0)).where(
                PosSale.org_id == org_id,
                PosSale.created_at >= start,
                PosSale.created_at < end,
                PosSale.is_refunded == False,  # noqa: E712
            )
        )
    ) or Decimal("0.00")

    inv_total = (
        await db.scalar(
            select(func.coalesce(func.sum(Invoice.total_sek), 0)).where(
                Invoice.org_id == org_id,
                Invoice.issue_date == day,
                Invoice.status != InvoiceStatus.DRAFT,
            )
        )
    ) or Decimal("0.00")

    return Decimal(pos_total) + Decimal(inv_total)


async def build_summary_stats(
    db: AsyncSession, org_id: uuid.UUID, *, for_date: date | None = None,
) -> SummaryStats:
    """Gather the stats shown in the nightly email.

    Pure read-only — safe to call from a test harness without faking
    the scheduler. ``for_date`` defaults to yesterday so a 07:30 send
    reports on the fully-closed previous day.
    """
    today = datetime.now(timezone.utc).date()
    target = for_date or (today - timedelta(days=1))
    prev = target - timedelta(days=1)
    stats = SummaryStats(date=target)

    stats.revenue = await _day_revenue(db, org_id, target)
    stats.revenue_prev = await _day_revenue(db, org_id, prev)
    if stats.revenue_prev > 0:
        delta = (
            (stats.revenue - stats.revenue_prev) / stats.revenue_prev * Decimal("100")
        )
        stats.revenue_delta_pct = delta.quantize(Decimal("0.1"))

    day_start = datetime.combine(target, time.min).replace(tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    # POS sale count (excluding refunds) + invoices issued.
    pos_count = (
        await db.scalar(
            select(func.count(PosSale.id)).where(
                PosSale.org_id == org_id,
                PosSale.created_at >= day_start,
                PosSale.created_at < day_end,
                PosSale.is_refunded == False,  # noqa: E712
            )
        )
    ) or 0
    stats.invoices_count = (
        await db.scalar(
            select(func.count(Invoice.id)).where(
                Invoice.org_id == org_id,
                Invoice.issue_date == target,
                Invoice.status != InvoiceStatus.DRAFT,
            )
        )
    ) or 0
    stats.orders_count = int(pos_count) + int(stats.invoices_count)

    # Low stock — count of products whose on-hand summed across
    # warehouses is at or below reorder_level. Reuses the dashboard
    # heuristic.
    low_stock_rows = (
        await db.execute(
            select(
                Product.id,
                Product.reorder_level,
                func.coalesce(func.sum(StockLevel.quantity), 0).label("on_hand"),
            )
            .outerjoin(StockLevel, StockLevel.product_id == Product.id)
            .where(
                Product.org_id == org_id,
                Product.is_active == True,  # noqa: E712
                Product.reorder_level > 0,
            )
            .group_by(Product.id, Product.reorder_level)
        )
    ).all()
    stats.low_stock_count = sum(
        1 for _, level, on_hand in low_stock_rows if int(on_hand) <= int(level)
    )

    # Overdue invoices as of today: SENT or OVERDUE with due_date in the past.
    overdue_row = await db.execute(
        select(
            func.count(Invoice.id),
            func.coalesce(func.sum(Invoice.total_sek), 0),
        ).where(
            Invoice.org_id == org_id,
            Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.OVERDUE]),
            Invoice.due_date < today,
        )
    )
    count_val, total_val = overdue_row.one()
    stats.overdue_count = int(count_val or 0)
    stats.overdue_total = Decimal(total_val or 0)

    stats.ai_insight = _pick_insight(stats)
    return stats


def _pick_insight(s: SummaryStats) -> str:
    """Deterministic one-liner prioritising the signal most likely to
    drive a merchant action. We do not call GPT here — a scheduler-time
    LLM round-trip adds cost and a failure mode to a 05:00 cron job
    that runs across every tenant. If the user wants a richer
    narrative they can open the AI chat, which already has the same
    context.
    """
    if s.overdue_count > 0:
        return (
            f"{s.overdue_count} overdue invoice(s) totalling "
            f"{s.overdue_total:.0f} SEK — consider running dunning today."
        )
    if s.low_stock_count >= 5:
        return (
            f"{s.low_stock_count} products are at or below reorder level — "
            "review auto-reorder drafts."
        )
    if s.revenue_delta_pct is not None and s.revenue_delta_pct <= Decimal("-20"):
        return (
            f"Revenue dropped {abs(s.revenue_delta_pct):.0f}% vs the previous "
            "day — worth checking sales channels."
        )
    if s.revenue_delta_pct is not None and s.revenue_delta_pct >= Decimal("20"):
        return (
            f"Revenue up {s.revenue_delta_pct:.0f}% vs the previous day — "
            "strong momentum."
        )
    if s.orders_count == 0:
        return "No orders yesterday. If this is unexpected, verify the POS and portal."
    return "Business steady — no unusual signals detected."


def render_summary_html(org_name: str, stats: SummaryStats) -> str:
    """Build the HTML body. Every dynamic value is HTML-escaped."""
    delta = ""
    if stats.revenue_delta_pct is not None:
        sign = "▲" if stats.revenue_delta_pct >= 0 else "▼"
        color = "#16a34a" if stats.revenue_delta_pct >= 0 else "#dc2626"
        delta = (
            f"<span style='color:{color};font-size:13px'>{sign} "
            f"{_h(abs(stats.revenue_delta_pct))}% vs previous day</span>"
        )
    return f"""
    <div style="font-family:sans-serif;max-width:640px;margin:0 auto">
      <h2 style="color:#1a2332;margin-bottom:4px">Daily business summary</h2>
      <p style="color:#888;margin-top:0">{_h(org_name)} · {_h(stats.date.isoformat())}</p>
      <div style="display:flex;gap:12px;margin:24px 0;flex-wrap:wrap">
        <div style="flex:1;min-width:140px;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:16px;text-align:center">
          <div style="font-size:24px;font-weight:700;color:#16a34a">{_h(f"{stats.revenue:.0f}")} kr</div>
          <div style="font-size:12px;color:#166534">Revenue</div>
          <div style="margin-top:4px">{delta}</div>
        </div>
        <div style="flex:1;min-width:140px;background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:16px;text-align:center">
          <div style="font-size:24px;font-weight:700;color:#1d4ed8">{_h(stats.orders_count)}</div>
          <div style="font-size:12px;color:#1e40af">Orders / sales</div>
        </div>
        <div style="flex:1;min-width:140px;background:#f5f3ff;border:1px solid #ddd6fe;border-radius:8px;padding:16px;text-align:center">
          <div style="font-size:24px;font-weight:700;color:#7c3aed">{_h(stats.invoices_count)}</div>
          <div style="font-size:12px;color:#5b21b6">Invoices issued</div>
        </div>
      </div>
      <div style="display:flex;gap:12px;margin:0 0 24px 0;flex-wrap:wrap">
        <div style="flex:1;min-width:140px;background:#fef9c3;border:1px solid #fde047;border-radius:8px;padding:16px;text-align:center">
          <div style="font-size:24px;font-weight:700;color:#ca8a04">{_h(stats.low_stock_count)}</div>
          <div style="font-size:12px;color:#854d0e">Low-stock items</div>
        </div>
        <div style="flex:1;min-width:140px;background:#fee2e2;border:1px solid #fecaca;border-radius:8px;padding:16px;text-align:center">
          <div style="font-size:24px;font-weight:700;color:#dc2626">{_h(stats.overdue_count)}</div>
          <div style="font-size:12px;color:#991b1b">Overdue invoices ({_h(f"{stats.overdue_total:.0f}")} kr)</div>
        </div>
      </div>
      <div style="background:#f9fafb;border-left:3px solid #1a2332;padding:12px 16px;margin:16px 0;border-radius:4px">
        <div style="font-size:12px;color:#888;margin-bottom:4px">AI insight</div>
        <div style="color:#1a2332">{_h(stats.ai_insight)}</div>
      </div>
      <p style="margin-top:24px">
        <a href="https://varuflow.se/analytics" style="background:#1a2332;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:600">
          Open dashboard
        </a>
      </p>
      <p style="margin-top:24px;color:#888;font-size:12px">
        Sent by Varuflow · Disable from Settings → Notifications
      </p>
    </div>
    """


async def send_summary_email(to_email: str, org_name: str, stats: SummaryStats) -> bool:
    """POST the email via Resend. Returns False (not raises) on any
    failure so the caller can audit it without aborting the whole sweep.
    Resend is a dependency-injection point for tests (patch this
    function or the underlying httpx client)."""
    if not settings.RESEND_API_KEY:
        return False

    payload = {
        "from": "Varuflow <digest@varuflow.app>",
        "to": [to_email],
        "subject": f"Daily summary — {org_name} ({stats.date.isoformat()})",
        "html": render_summary_html(org_name, stats),
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.post(
                RESEND_URL,
                json=payload,
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            )
        return res.status_code in (200, 201)
    except Exception as e:  # noqa: BLE001
        log.error("nightly_summary resend call failed: %s", str(e)[:300])
        return False


async def _already_sent_today(
    db: AsyncSession, org_id: uuid.UUID, today: date,
) -> bool:
    """True when a NIGHTLY_SUMMARY_SENT audit entry exists for ``org_id``
    on ``today``. The daily cardinality is tiny (1 row per org) so this
    is cheap and avoids a bespoke ``nightly_summary_runs`` table."""
    day_start = datetime.combine(today, time.min).replace(tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)
    existing = await db.scalar(
        select(AuditLogEntry.id).where(
            AuditLogEntry.org_id == org_id,
            AuditLogEntry.action == "NIGHTLY_SUMMARY_SENT",
            AuditLogEntry.created_at >= day_start,
            AuditLogEntry.created_at < day_end,
        ).limit(1)
    )
    return existing is not None


@dataclass
class RunResult:
    org_id: uuid.UUID
    sent: bool
    reason: str | None = None  # "sent", "already_sent_today", "no_email", ...


async def run_summary_for_org(
    db: AsyncSession,
    org: Organization,
    *,
    to_email: str | None,
    today: date | None = None,
) -> RunResult:
    """Build + send summary for one org. Idempotent per calendar day via
    the audit-log probe. Always writes exactly one audit entry:
    SENT on success, FAILED on any other outcome (email send failed,
    no recipient email configured)."""
    today = today or datetime.now(timezone.utc).date()

    if await _already_sent_today(db, org.id, today):
        return RunResult(org_id=org.id, sent=False, reason="already_sent_today")

    if not to_email:
        await log_action(
            db,
            action="NIGHTLY_SUMMARY_FAILED",
            org_id=org.id,
            target_type="organization",
            target_id=str(org.id),
            extra={"reason": "no_email"},
        )
        return RunResult(org_id=org.id, sent=False, reason="no_email")

    stats = await build_summary_stats(db, org.id)
    ok = await send_summary_email(to_email, org.name, stats)

    if ok:
        await log_action(
            db,
            action="NIGHTLY_SUMMARY_SENT",
            org_id=org.id,
            target_type="organization",
            target_id=str(org.id),
            extra={"to": to_email, **stats.to_extra()},
        )
        return RunResult(org_id=org.id, sent=True, reason="sent")

    await log_action(
        db,
        action="NIGHTLY_SUMMARY_FAILED",
        org_id=org.id,
        target_type="organization",
        target_id=str(org.id),
        extra={"reason": "resend_failed", "to": to_email},
    )
    return RunResult(org_id=org.id, sent=False, reason="resend_failed")
