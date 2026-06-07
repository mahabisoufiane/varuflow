"""Background scheduler: Fortnox sync, low-stock alerts, weekly digest.

Multi-instance safety
---------------------
Each job acquires a PostgreSQL advisory lock before running. Only the
replica that wins `pg_try_advisory_lock()` executes the job; the others
skip silently. This avoids duplicate emails when Railway scales out.

The lock IDs below must be stable 64-bit integers; changing them mid-flight
would allow two replicas to run the same job until all replicas redeploy.
"""
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import engine

logger = logging.getLogger(__name__)

_SessionLocal: async_sessionmaker[AsyncSession] | None = None

# Stable 64-bit advisory-lock IDs — DO NOT renumber without a coordinated deploy
_LOCK_FORTNOX = 811_001
_LOCK_LOWSTOCK = 811_002
_LOCK_DIGEST = 811_003
_LOCK_TOKEN_CLEANUP = 811_004
_LOCK_BOKFORING_REMINDER = 811_005
_LOCK_DUNNING = 811_006
_LOCK_PUSH_STOCKOUT = 811_007
_LOCK_PUSH_OVERDUE = 811_008
_LOCK_ONBOARDING_REMINDER = 811_009
_LOCK_WEBHOOK_RETRY = 811_010
_LOCK_HEALTH_PROBE = 811_011
_LOCK_STOCK_COUNT_STUCK = 811_012
_LOCK_AUTO_REORDER = 811_013
_LOCK_RECURRING_AUTOSEND = 811_014
_LOCK_NIGHTLY_SUMMARY = 811_015
_LOCK_BOOKING_REMINDERS = 811_016
_LOCK_COMMISSION_MONTHLY = 811_017
_LOCK_GIFTCARD_EXPIRY = 811_018
_LOCK_EXCHANGE_RATES = 811_019
_LOCK_LOYALTY_EXPIRY = 811_020
_LOCK_SEGMENT_REFRESH = 811_021
_LOCK_CAMPAIGN_DISPATCH = 811_022
_LOCK_REVIEW_REQUEST_SWEEP = 811_023
_LOCK_SUBSCRIPTION_PAUSE_SWEEP = 811_024
_LOCK_ABANDONED_CART = 811_025
_LOCK_EMAIL_SEQUENCE_DRIP = 811_026
_LOCK_QUOTE_EXPIRY = 811_027
_LOCK_TRIAL_SWEEP = 811_028
_LOCK_PARTNER_COMMISSIONS = 811_029
_LOCK_OPERATOR_COMMISSIONS = 811_030
_LOCK_NPS_HEALTH = 811_031
_LOCK_NPS_REMINDER = 811_032
_LOCK_TRIAL_ONBOARDING = 811_033


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    return _SessionLocal


async def _org_notification_email(db: AsyncSession, org_id) -> str | None:
    """Return an email address to deliver scheduled notifications to, or None.

    Organization has no dedicated `billing_email` column, so we derive the
    destination from the OWNER membership's local-auth record. Earlier
    revisions of this file referenced `org.billing_email` directly — that
    attribute does not exist on the ORM model, so every dereference raised
    AttributeError and was swallowed by the enclosing `except Exception`,
    silently killing every low-stock and weekly-digest delivery.

    Supabase-only users have no AuthUser row; for those orgs we return None
    and the caller skips. Adding a Supabase admin lookup here would require
    the service-role key and a network call per org, which is disallowed
    from the scheduler context.
    """
    # Local imports to avoid a circular import at module load time —
    # app.models.auth transitively imports app.database which re-enters this
    # module during the initial import cycle on cold starts.
    from app.models.auth import AuthUser
    from app.models.organization import OrganizationMember, OrgRole

    row = await db.execute(
        select(AuthUser.email)
        .join(OrganizationMember, OrganizationMember.user_id == AuthUser.id)
        .where(
            OrganizationMember.org_id == org_id,
            OrganizationMember.role == OrgRole.OWNER,
        )
        .order_by(OrganizationMember.created_at.asc())
        .limit(1)
    )
    email = row.scalar_one_or_none()
    return email or None


async def _with_advisory_lock(lock_id: int, job_name: str, coro_factory) -> None:
    """Run `coro_factory(db)` only if we acquire advisory lock `lock_id`.

    The lock is automatically released when the connection is returned to
    the pool at the end of the async-with block. SQLite test databases do
    not implement pg_try_advisory_lock — fall back to running unconditionally.
    """
    session_factory = _get_session_factory()
    async with session_factory() as db:
        try:
            result = await db.execute(
                text("SELECT pg_try_advisory_lock(:lid)").bindparams(lid=lock_id)
            )
            got_lock = bool(result.scalar())
        except Exception:
            # Non-Postgres driver (tests) — just run the job
            got_lock = True

        if not got_lock:
            logger.info("%s skipped — another replica holds the lock", job_name)
            return

        try:
            await coro_factory(db)
        finally:
            try:
                await db.execute(
                    text("SELECT pg_advisory_unlock(:lid)").bindparams(lid=lock_id)
                )
            except Exception:
                pass


# ── Jobs ─────────────────────────────────────────────────────────────────────

async def _sync_fortnox() -> None:
    """Sync invoices for all orgs that have an active Fortnox connection."""
    from app.models.organization import Organization

    async def _impl(db):
        try:
            result = await db.execute(
                select(Organization).where(Organization.fortnox_access_token.isnot(None))
            )
            orgs = result.scalars().all()
            logger.info("Fortnox sync: %d orgs with active token", len(orgs))
            # Full sync logic runs via the integrations router on-demand.
            # This job refreshes expiring tokens so they stay valid.
            for org in orgs:
                try:
                    if org.fortnox_token_expiry and org.fortnox_token_expiry < datetime.now(timezone.utc):
                        logger.info("Fortnox token expired for org %s — needs re-auth", org.id)  # nosemgrep: python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure
                except Exception:
                    logger.exception("Fortnox token check failed for org %s", org.id)  # nosemgrep: python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure
        except Exception:
            logger.exception("Fortnox sync job failed")

    await _with_advisory_lock(_LOCK_FORTNOX, "fortnox_sync", _impl)


async def _check_low_stock() -> None:
    """Email orgs whose products have fallen below reorder_level."""
    from app.models.inventory import Product, StockLevel
    from app.models.organization import Organization
    from app.models.idempotency import IdempotencyKey
    from app.services.email import send_low_stock_alert_email
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    async def _impl(db):
        try:
            # Find products below reorder_level grouped by org
            rows = await db.execute(
                select(
                    Product.org_id,
                    Product.name,
                    Product.sku,
                    Product.reorder_level,
                    func.coalesce(func.sum(StockLevel.quantity), 0).label("total_stock"),
                )
                .outerjoin(StockLevel, StockLevel.product_id == Product.id)
                .where(Product.is_active == True, Product.reorder_level > 0)  # noqa: E712
                .group_by(Product.org_id, Product.id, Product.name, Product.sku, Product.reorder_level)
                .having(func.coalesce(func.sum(StockLevel.quantity), 0) <= Product.reorder_level)
            )
            low = rows.all()

            # Group by org
            by_org: dict = {}
            for row in low:
                by_org.setdefault(row.org_id, []).append({
                    "name": row.name,
                    "sku": row.sku,
                    "stock": int(row.total_stock),
                    "reorder_level": int(row.reorder_level),
                })

            # De-spam: only email each org at most once per ISO week. This
            # job runs daily, but the same product hovering below reorder
            # level would otherwise trigger 7 identical alert emails per
            # week — burying real signals and looking like spam. Acquire
            # the dedupe slot atomically via INSERT ON CONFLICT so two
            # concurrent scheduler processes can't both send.
            today = datetime.now(timezone.utc).date()
            week_key = f"{today.isocalendar().year}-W{today.isocalendar().week:02d}"
            for org_id, items in by_org.items():
                org = await db.get(Organization, org_id)
                if not org or not org.is_active:
                    continue
                to_email = await _org_notification_email(db, org_id)
                if not to_email:
                    continue
                dedupe_key = f"low_stock:{week_key}"
                slot = await db.execute(
                    pg_insert(IdempotencyKey.__table__)
                    .values(
                        org_id=org_id,
                        endpoint="scheduler.low_stock_alert",
                        key=dedupe_key,
                        target_id=str(today),
                    )
                    .on_conflict_do_nothing(index_elements=["org_id", "endpoint", "key"])
                )
                if slot.rowcount == 0:
                    # Already sent this week for this org — skip.
                    continue
                # Commit the slot immediately so a crash/failure below
                # doesn't resend — the cleanup job prunes old slots after
                # ~30 days, well beyond the weekly cadence.
                await db.commit()
                await send_low_stock_alert_email(
                    to_email=to_email,
                    org_name=org.name,
                    low_stock_items=items,
                )
                logger.info("Low-stock alert sent to %s (%d items)", org.name, len(items))
        except Exception:
            logger.exception("Low-stock check job failed")

    await _with_advisory_lock(_LOCK_LOWSTOCK, "low_stock_check", _impl)


async def _send_weekly_digest() -> None:
    """Send a weekly business digest to each org's billing email."""
    from app.models.inventory import Product, StockLevel
    from app.models.organization import Organization
    from app.models.pos import PosSale, PosSaleItem
    from app.models.idempotency import IdempotencyKey
    from app.services.email import send_weekly_digest_email
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    async def _impl(db):
        try:
            orgs_result = await db.execute(select(Organization))
            orgs = orgs_result.scalars().all()

            week_start = datetime.now(timezone.utc) - timedelta(days=7)
            week_ending = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            # Per-org weekly dedupe: the cron fires Mon 08:00 Stockholm
            # with a 1 h misfire grace, so a restart or deploy during the
            # window can re-run the job. Without this guard, every re-run
            # re-emails every org with the same digest. Matches the
            # weekly dedupe pattern already used by _check_low_stock.
            today = datetime.now(timezone.utc).date()
            week_key = f"{today.isocalendar().year}-W{today.isocalendar().week:02d}"

            for org in orgs:
                if not org.is_active:
                    continue
                to_email = await _org_notification_email(db, org.id)
                if not to_email:
                    continue
                dedupe_key = f"weekly_digest:{week_key}"
                slot = await db.execute(
                    pg_insert(IdempotencyKey.__table__)
                    .values(
                        org_id=org.id,
                        endpoint="scheduler.weekly_digest",
                        key=dedupe_key,
                        target_id=str(today),
                    )
                    .on_conflict_do_nothing(index_elements=["org_id", "endpoint", "key"])
                )
                if slot.rowcount == 0:
                    # Already sent this week for this org — skip.
                    continue
                # Commit the slot immediately so a failure below doesn't
                # trigger a resend. The cleanup job prunes the row after
                # 7 days, well past the weekly cadence.
                await db.commit()
                try:
                    # Revenue + sale count for last 7 days. Exclude
                    # refunded sales so the digest matches the
                    # Z-report / session summary shown in the app
                    # (prior round fixed the same inflation bug in
                    # pos.py::SessionOut). Otherwise an owner sees
                    # "50k revenue" here while the dashboard and the
                    # printed Z-report both show net — and the
                    # numbers disagree.
                    rev_row = await db.execute(
                        select(
                            func.coalesce(func.sum(PosSale.total), 0).label("revenue"),
                            func.count(PosSale.id).label("cnt"),
                        ).where(
                            PosSale.org_id == org.id,
                            PosSale.created_at >= week_start,
                            PosSale.is_refunded == False,  # noqa: E712
                        )
                    )
                    rev = rev_row.one()

                    # Top 5 products by quantity sold (also excluding
                    # refunded sales — a 500-unit sale that was refunded
                    # the next day shouldn't top the weekly leaderboard).
                    top_result = await db.execute(
                        select(
                            PosSaleItem.description,
                            func.sum(PosSaleItem.quantity).label("qty"),
                        )
                        .join(PosSale, PosSale.id == PosSaleItem.sale_id)
                        .where(
                            PosSale.org_id == org.id,
                            PosSale.created_at >= week_start,
                            PosSale.is_refunded == False,  # noqa: E712
                        )
                        .group_by(PosSaleItem.description)
                        .order_by(func.sum(PosSaleItem.quantity).desc())
                        .limit(5)
                    )
                    top_products = [
                        {"name": r.description, "quantity": int(r.qty)}
                        for r in top_result.all()
                    ]

                    # Low-stock count
                    # Count products whose summed stock across all warehouses
                    # is at or below their reorder_level. The previous version
                    # used GROUP BY Product.id, which made `db.scalar()` return
                    # the count of the *first* product group (always 1), so
                    # the digest's low_stock_count was effectively a broken
                    # boolean. Wrap the per-product query in a subquery and
                    # COUNT the rows it produces.
                    low_subq = (
                        select(Product.id)
                        .outerjoin(StockLevel, StockLevel.product_id == Product.id)
                        .where(
                            Product.org_id == org.id,
                            Product.is_active == True,  # noqa: E712
                            Product.reorder_level > 0,
                        )
                        .group_by(Product.id, Product.reorder_level)
                        .having(
                            func.coalesce(func.sum(StockLevel.quantity), 0)
                            <= Product.reorder_level
                        )
                        .subquery()
                    )
                    low_count = await db.scalar(
                        select(func.count()).select_from(low_subq)
                    ) or 0

                    await send_weekly_digest_email(
                        to_email=to_email,
                        org_name=org.name,
                        stats={
                            "revenue": f"{rev.revenue:,.0f}",
                            "sales_count": int(rev.cnt),
                            "top_products": top_products,
                            "low_stock_count": int(low_count),
                            "week_ending": week_ending,
                        },
                    )
                    logger.info("Weekly digest sent to %s", org.name)
                except Exception:
                    logger.exception("Weekly digest failed for org %s", org.id)
        except Exception:
            logger.exception("Weekly digest job failed")

    await _with_advisory_lock(_LOCK_DIGEST, "weekly_digest", _impl)


async def _cleanup_stale_tokens() -> None:
    """Delete expired/revoked auth refresh tokens, used/expired portal tokens,
    consumed OAuth state rows, and old Stripe processed-event markers.

    Keeping these rows forever bloats indexes and leaks minor metadata.
    Runs daily at 03:00 Stockholm when traffic is lowest.
    """
    from sqlalchemy import delete

    async def _impl(db):
        now = datetime.now(timezone.utc)
        cutoff_30d = now - timedelta(days=30)

        deleted_counts: dict[str, int] = {}

        try:
            from app.models.auth import AuthRefreshToken
            r = await db.execute(
                delete(AuthRefreshToken).where(
                    (AuthRefreshToken.revoked == True) |  # noqa: E712
                    (AuthRefreshToken.expires_at < cutoff_30d)
                )
            )
            deleted_counts["refresh_tokens"] = r.rowcount or 0
        except Exception:
            logger.exception("refresh token cleanup failed")

        try:
            from app.models.invoicing import CustomerPortalToken
            r = await db.execute(
                delete(CustomerPortalToken).where(
                    (CustomerPortalToken.used == True) |  # noqa: E712
                    (CustomerPortalToken.expires_at < now)
                )
            )
            deleted_counts["portal_tokens"] = r.rowcount or 0
        except Exception:
            logger.exception("portal token cleanup failed")

        try:
            from app.models.organization import FortnoxOAuthState
            # Delete any state row past its expires_at — they are single-use
            # CSRF nonces with a 10-minute TTL.
            r = await db.execute(
                delete(FortnoxOAuthState).where(FortnoxOAuthState.expires_at < now)
            )
            deleted_counts["fortnox_oauth_state"] = r.rowcount or 0
        except Exception:
            # Model/table may not exist in some installs — non-fatal
            pass

        try:
            # Idempotency keys: retain short-lived keys for 7 days. After
            # that the client has either retried or moved on; no real-world
            # retry window is longer.
            #
            # EXCEPT for endpoints that mark a permanent business-record
            # event (e.g. "this invoice has been pushed to Fortnox"). Those
            # rows must survive forever — deleting them causes the next
            # sync click to re-push the same invoice to the upstream
            # bookkeeping system, producing duplicate invoices that the
            # customer then has to unwind by hand. Fortnox does not dedupe
            # on YourReference, so the idempotency row here IS the
            # deduplication guarantee. Keep this allow-list in sync with
            # any new "permanent" idempotency endpoints.
            from app.models.idempotency import IdempotencyKey
            _PERMANENT_IDEMPOTENCY_ENDPOINTS = {
                "integrations.fortnox_sync_invoice",
            }
            cutoff_7d = now - timedelta(days=7)
            r = await db.execute(
                delete(IdempotencyKey).where(
                    IdempotencyKey.created_at < cutoff_7d,
                    ~IdempotencyKey.endpoint.in_(_PERMANENT_IDEMPOTENCY_ENDPOINTS),
                )
            )
            deleted_counts["idempotency_keys"] = r.rowcount or 0
        except Exception:
            logger.exception("idempotency key cleanup failed")

        try:
            # Stripe processed-event markers: retain for 45 days (Stripe's
            # replay window is 30 days; +15d buffer for clock skew / extended
            # retries during an outage).
            from app.routers.billing import StripeProcessedEvent
            cutoff_45d = now - timedelta(days=45)
            r = await db.execute(
                delete(StripeProcessedEvent).where(StripeProcessedEvent.created_at < cutoff_45d)
            )
            deleted_counts["stripe_events"] = r.rowcount or 0
        except Exception:
            logger.exception("stripe event cleanup failed")

        await db.commit()
        logger.info("token_cleanup deleted=%s", deleted_counts)  # nosemgrep: python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure

    await _with_advisory_lock(_LOCK_TOKEN_CLEANUP, "token_cleanup", _impl)


async def _bokforing_reminder() -> None:
    """Send every org owner a yearly nudge to run the bokföring export.

    Triggered once a year by the scheduler (Jan 15 08:00 Europe/Stockholm).
    Each owner email is sent at most once per year via the idempotency
    table so concurrent replicas / misfired retries cannot double-send.
    """
    from app.models.idempotency import IdempotencyKey
    from app.models.organization import Organization
    from app.services.email import send_bokforing_reminder_email
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    async def _impl(db):
        try:
            year = datetime.now(timezone.utc).year
            orgs = (
                await db.scalars(
                    select(Organization).where(Organization.is_active == True)  # noqa: E712
                )
            ).all()
            for org in orgs:
                try:
                    to_email = await _org_notification_email(db, org.id)
                    if not to_email:
                        continue
                    slot = await db.execute(
                        pg_insert(IdempotencyKey.__table__)
                        .values(
                            org_id=org.id,
                            endpoint="scheduler.bokforing_reminder",
                            key=f"bokforing:{year}",
                            target_id=str(year),
                        )
                        .on_conflict_do_nothing(index_elements=["org_id", "endpoint", "key"])
                    )
                    if slot.rowcount == 0:
                        continue  # already sent this year
                    await send_bokforing_reminder_email(
                        to_email=to_email,
                        org_name=org.name,
                        year=year,
                    )
                    logger.info("bokforing_reminder sent org=%s year=%d", org.id, year)
                except Exception:
                    logger.exception("bokforing_reminder failed for org %s", org.id)
            await db.commit()
        except Exception:
            logger.exception("bokforing_reminder job failed")

    await _with_advisory_lock(_LOCK_BOKFORING_REMINDER, "bokforing_reminder", _impl)


async def _run_dunning() -> None:
    """Daily dunning sweep — email overdue invoice customers.

    Stage idempotency is enforced by ``uq_dunning_events_invoice_stage``
    so concurrent replicas and scheduler misfires cannot double-send.
    """
    from app.services.dunning import run_dunning_sweep

    async def _impl(db):
        try:
            stats = await run_dunning_sweep(db)
            logger.info("dunning sweep %s", stats)
        except Exception:
            logger.exception("dunning sweep failed")

    await _with_advisory_lock(_LOCK_DUNNING, "dunning_sweep", _impl)


async def _push_stockout_imminent() -> None:
    """Push mobile alerts for products running out within 7 days.

    Mirrors the ``demand_forecast`` card in ``routers/ai_engine.py`` so
    the mobile push matches the AI-engine HIGH-priority threshold. One
    push per (org, product) per ISO week — dedupe uses IdempotencyKey
    the same way as ``_check_low_stock``.

    Distinct from the low-stock email which is triggered by
    ``stock <= reorder_level``; stockout-imminent uses a velocity-based
    forecast so it fires earlier for fast-moving SKUs and may stay
    silent for slow movers that a simple threshold would flag.
    """
    from app.models.inventory import Product, StockLevel, StockMovement
    from app.models.organization import OrgRole
    from app.models.idempotency import IdempotencyKey
    from app.services.push import send_to_org_members
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    async def _impl(db):
        try:
            # Velocity = units moved OUT over the last 30 days.
            # Matches the formula used in ai_engine.demand_forecast.
            window_start = datetime.now(timezone.utc) - timedelta(days=30)
            stock_rows = await db.execute(
                select(
                    Product.id,
                    Product.org_id,
                    Product.name,
                    func.coalesce(func.sum(StockLevel.quantity), 0).label("stock"),
                )
                .outerjoin(StockLevel, StockLevel.product_id == Product.id)
                .where(Product.is_active == True)  # noqa: E712
                .group_by(Product.id, Product.org_id, Product.name)
            )
            products = stock_rows.all()
            if not products:
                return

            today = datetime.now(timezone.utc).date()
            week_key = f"{today.isocalendar().year}-W{today.isocalendar().week:02d}"

            for p in products:
                mv = await db.execute(
                    select(func.coalesce(func.sum(StockMovement.quantity), 0))
                    .where(
                        StockMovement.product_id == p.id,
                        StockMovement.quantity < 0,
                        StockMovement.created_at >= window_start,
                    )
                )
                outflow = abs(int(mv.scalar() or 0))
                if outflow == 0:
                    continue
                daily = outflow / 30.0
                days_until = (int(p.stock) / daily) if daily > 0 else None
                if days_until is None or days_until >= 7:
                    continue

                dedupe_key = f"push_stockout:{week_key}:{p.id}"
                slot = await db.execute(
                    pg_insert(IdempotencyKey.__table__)
                    .values(
                        org_id=p.org_id,
                        endpoint="scheduler.push_stockout",
                        key=dedupe_key,
                        target_id=str(p.id),
                    )
                    .on_conflict_do_nothing(index_elements=["org_id", "endpoint", "key"])
                )
                if slot.rowcount == 0:
                    continue
                await db.commit()

                await send_to_org_members(
                    db,
                    org_id=p.org_id,
                    event="stockout",
                    title="Slutar snart i lager",
                    body=f"{p.name}: ca {round(days_until, 1)} dagar kvar",
                    data={
                        "type": "stockout",
                        "product_id": str(p.id),
                        "days_until_stockout": round(days_until, 1),
                    },
                    roles=[OrgRole.OWNER, OrgRole.ADMIN],
                )
        except Exception:
            logger.exception("push stockout job failed")

    await _with_advisory_lock(_LOCK_PUSH_STOCKOUT, "push_stockout", _impl)


async def _push_overdue_invoices() -> None:
    """Push when an invoice first crosses D+1 overdue.

    The dunning email ladder starts at D+3 (stage 1). This job exists
    so mobile users get a same-week heads-up before the first customer
    email goes out. Dedupe key is per-invoice, not per-day, so a single
    push is sent per invoice regardless of how many times the job runs.
    """
    from app.models.invoicing import Invoice, InvoiceStatus
    from app.models.organization import OrgRole
    from app.models.idempotency import IdempotencyKey
    from app.services.push import send_to_org_members
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    async def _impl(db):
        try:
            target = (datetime.now(timezone.utc).date()) - timedelta(days=1)
            rows = await db.execute(
                select(Invoice).where(
                    Invoice.due_date == target,
                    Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.OVERDUE]),
                )
            )
            invoices = rows.scalars().all()
            for inv in invoices:
                dedupe_key = f"push_overdue:{inv.id}"
                slot = await db.execute(
                    pg_insert(IdempotencyKey.__table__)
                    .values(
                        org_id=inv.org_id,
                        endpoint="scheduler.push_overdue",
                        key=dedupe_key,
                        target_id=str(inv.id),
                    )
                    .on_conflict_do_nothing(index_elements=["org_id", "endpoint", "key"])
                )
                if slot.rowcount == 0:
                    continue
                await db.commit()
                await send_to_org_members(
                    db,
                    org_id=inv.org_id,
                    event="overdue",
                    title="Faktura förfallen",
                    body=f"Faktura {inv.invoice_number} är 1 dag försenad",
                    data={
                        "type": "overdue",
                        "invoice_id": str(inv.id),
                        "invoice_number": inv.invoice_number,
                    },
                    roles=[OrgRole.OWNER, OrgRole.ADMIN],
                )
        except Exception:
            logger.exception("push overdue job failed")

    await _with_advisory_lock(_LOCK_PUSH_OVERDUE, "push_overdue", _impl)


async def _send_onboarding_reminder() -> None:
    """Email orgs that signed up >48h ago and haven't completed any
    onboarding checklist step. Sent at most once per org — the
    IdempotencyKey row is the send ledger.
    """
    from app.models.organization import Organization
    from app.models.onboarding import OnboardingProgress
    from app.models.idempotency import IdempotencyKey
    from app.services.email import send_onboarding_reminder_email
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    async def _impl(db):
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
            rows = await db.execute(
                select(Organization).where(
                    Organization.created_at <= cutoff,
                    Organization.is_active == True,  # noqa: E712
                )
            )
            orgs = rows.scalars().all()
            if not orgs:
                return

            dashboard_url = "https://varuflow.se/dashboard"
            for org in orgs:
                # Skip orgs that have already completed at least one step.
                progressed = await db.execute(
                    select(func.count()).select_from(OnboardingProgress)
                    .where(OnboardingProgress.org_id == org.id)
                )
                if (progressed.scalar() or 0) > 0:
                    continue

                to_email = await _org_notification_email(db, org.id)
                if not to_email:
                    continue

                # IdempotencyKey is the one-shot ledger — trying to insert
                # a second time is a no-op, guaranteeing single delivery.
                slot = await db.execute(
                    pg_insert(IdempotencyKey.__table__)
                    .values(
                        org_id=org.id,
                        endpoint="scheduler.onboarding_reminder",
                        key="onboarding_reminder:v1",
                        target_id=str(org.id),
                    )
                    .on_conflict_do_nothing(index_elements=["org_id", "endpoint", "key"])
                )
                if slot.rowcount == 0:
                    continue
                await db.commit()

                await send_onboarding_reminder_email(
                    to_email=to_email,
                    org_name=org.name,
                    dashboard_url=dashboard_url,
                )
                logger.info("Onboarding reminder sent to %s", org.name)
        except Exception:
            logger.exception("Onboarding reminder job failed")

    await _with_advisory_lock(
        _LOCK_ONBOARDING_REMINDER, "onboarding_reminder", _impl
    )


async def _retry_webhooks() -> None:
    """Drive the webhook exponential-backoff retry queue.

    The dispatcher records each failed delivery's ``next_retry_at``; this
    job picks up everything due and re-attempts. Wrapped in the standard
    advisory lock so only one Railway replica drains the queue per tick.
    """
    from app.services.webhook_dispatcher import retry_pending

    async def _impl(db):
        try:
            count = await retry_pending(db)
            if count:
                logger.info("Webhook retry sweep processed %d delivery attempts", count)
        except Exception:
            logger.exception("Webhook retry sweep failed")

    await _with_advisory_lock(_LOCK_WEBHOOK_RETRY, "webhook_retry", _impl)


async def _run_health_probe() -> None:
    """Probe DB + external services and persist a HealthCheck row.

    Runs every 5 minutes. The advisory lock guarantees a single replica
    writes the row so the public /status timeline doesn't double-count.
    """
    from app.services.status_page import run_health_probe

    async def _impl(db):
        try:
            await run_health_probe(db)
        except Exception:
            logger.exception("Health probe failed")

    await _with_advisory_lock(_LOCK_HEALTH_PROBE, "health_probe", _impl)


# ── Item 14: stuck stock-count reset ─────────────────────────────────────────

async def _check_stuck_stock_counts() -> None:
    """Reset counts stuck in SUBMITTED for >24h back to DRAFT.

    Offline clients submit over the network; a partial submission (e.g.
    the device died between /submit and /sync) would otherwise leave
    the count in SUBMITTED forever and silently block re-attempts. This
    job puts such rows back into DRAFT so the next reconnect resumes
    the flow cleanly.
    """
    from app.routers.stock_counts import mark_stuck_counts

    async def _impl(db):
        try:
            n = await mark_stuck_counts(db, older_than_hours=24)
            if n:
                logger.info("stock_count_stuck_reset n=%d", n)
        except Exception:
            logger.exception("stock_count_stuck_reset failed")

    await _with_advisory_lock(
        _LOCK_STOCK_COUNT_STUCK, "stock_count_stuck", _impl
    )


# Mapping used by the auto-reorder sweep to translate today's weekday
# index into the MON..SUN codes stored on Organization.auto_reorder_days.
_WEEKDAY_CODES = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")


async def _auto_reorder_check() -> None:
    """Daily sweep — run auto_reorder for every org whose schedule
    matches today. Failures are isolated per org so one bad tenant
    never blocks the sweep for everyone else."""
    from app.models.organization import Organization
    from app.services.auto_reorder import run_auto_reorder

    async def _impl(db):
        try:
            orgs = (
                await db.scalars(
                    select(Organization).where(
                        Organization.is_active == True,  # noqa: E712
                        Organization.auto_reorder_enabled == True,  # noqa: E712
                    )
                )
            ).all()
            if not orgs:
                return
            today_code = _WEEKDAY_CODES[datetime.now(timezone.utc).weekday()]
            for org in orgs:
                day_set = {
                    d.strip().upper()
                    for d in (org.auto_reorder_days or "").split(",")
                    if d.strip()
                }
                if today_code not in day_set:
                    continue
                try:
                    await run_auto_reorder(org.id, db, triggered_by="scheduler")
                except Exception:
                    logger.exception(
                        "auto_reorder scheduler run failed org=%s", org.id
                    )
        except Exception:
            logger.exception("auto_reorder sweep failed")

    await _with_advisory_lock(_LOCK_AUTO_REORDER, "auto_reorder_check", _impl)


# ── Item 17: recurring invoice auto-send ─────────────────────────────────────

async def _recurring_autosend() -> None:
    """Daily sweep — for every active RecurringInvoice whose
    ``next_run_date <= today`` and ``auto_send`` is on, generate the
    invoice (factored helper) and dispatch through the configured
    channels. Per-schedule failures are isolated so one bad tenant does
    not block others; each schedule runs in its own mini-transaction
    holding a ``with_for_update`` row lock so a concurrent manual
    ``/run`` click and this sweep cannot double-mint the same invoice.
    """
    from app.models.invoicing import RecurringInvoice
    from app.services.recurring_send import (
        RecurringRunError,
        auto_send_invoice,
        generate_invoice_from_recurring,
    )

    async def _impl(db):
        try:
            today = datetime.now(timezone.utc).date()
            ids = (
                await db.scalars(
                    select(RecurringInvoice.id).where(
                        RecurringInvoice.is_active == True,  # noqa: E712
                        RecurringInvoice.auto_send == True,  # noqa: E712
                        RecurringInvoice.next_run_date <= today,
                    )
                )
            ).all()
            if not ids:
                return
            logger.info("recurring_autosend sweep candidates=%d", len(ids))

            session_factory = _get_session_factory()
            for rec_id in ids:
                # Fresh session per schedule so a rollback of one does
                # not poison the rest, mirroring the pattern used by the
                # auto-reorder sweep.
                async with session_factory() as inner:
                    try:
                        row = await inner.execute(
                            select(RecurringInvoice)
                            .where(RecurringInvoice.id == rec_id)
                            .with_for_update()
                        )
                        rec = row.scalar_one_or_none()
                        if rec is None:
                            continue
                        # Re-check: the schedule may have been paused or
                        # the due date already advanced by a manual /run
                        # between the candidate query and here.
                        if (
                            not rec.is_active
                            or not rec.auto_send
                            or rec.next_run_date > today
                        ):
                            continue

                        new_inv = await generate_invoice_from_recurring(
                            inner, recurring=rec, org_id=rec.org_id
                        )
                        await inner.commit()

                        await auto_send_invoice(
                            inner, recurring=rec, invoice_id=new_inv.id
                        )
                    except RecurringRunError as exc:
                        logger.warning(
                            "recurring_autosend skipped rec=%s reason=%s",
                            rec_id,
                            exc.reason,
                        )
                        await inner.rollback()
                    except Exception:
                        logger.exception(
                            "recurring_autosend run failed rec=%s", rec_id
                        )
                        try:
                            await inner.rollback()
                        except Exception:
                            pass
        except Exception:
            logger.exception("recurring_autosend sweep failed")

    await _with_advisory_lock(
        _LOCK_RECURRING_AUTOSEND, "recurring_autosend", _impl
    )


# ── Item 21: nightly business summary email ──────────────────────────────────

async def _nightly_summary_sweep() -> None:
    """15-minute sweep. For each org whose ``nightly_summary_enabled``
    is True and whose configured ``nightly_summary_time`` falls inside
    the current 15-min window (local Europe/Stockholm), build and send
    a daily summary. Idempotency is enforced by the service itself via
    an audit-log probe, so a scheduler misfire cannot double-send.
    """
    from zoneinfo import ZoneInfo

    from app.models.organization import Organization
    from app.services.nightly_summary import run_summary_for_org

    async def _impl(db):
        try:
            # Pull candidates first — tiny result set (bound by enabled
            # orgs), and doing it in bulk keeps the per-org loop cheap.
            orgs = (
                await db.scalars(
                    select(Organization).where(
                        Organization.is_active == True,  # noqa: E712
                        Organization.nightly_summary_enabled == True,  # noqa: E712
                    )
                )
            ).all()
            if not orgs:
                return

            tz = ZoneInfo("Europe/Stockholm")
            now_local = datetime.now(tz)
            # Window is [floor(15-min), floor(15-min)+15m). A scheduler
            # running every 15 min guarantees each configured time hits
            # exactly one window. Slightly wider tolerance (e.g. 20 min)
            # would let a misfire re-enter the window and attempt to send
            # twice — defensible since the audit probe also guards, but
            # tight bounds are simpler to reason about.
            window_minutes = 15
            window_start = now_local.replace(
                minute=(now_local.minute // window_minutes) * window_minutes,
                second=0, microsecond=0,
            )
            window_end = window_start + timedelta(minutes=window_minutes)

            for org in orgs:
                cfg_time = org.nightly_summary_time
                fire_at = now_local.replace(
                    hour=cfg_time.hour,
                    minute=cfg_time.minute,
                    second=0,
                    microsecond=0,
                )
                if not (window_start <= fire_at < window_end):
                    continue

                to_email = await _org_notification_email(db, org.id)
                try:
                    await run_summary_for_org(db, org, to_email=to_email)
                    await db.commit()
                except Exception:
                    await db.rollback()
                    logger.exception(
                        "nightly_summary send failed org=%s", org.id
                    )
        except Exception:
            logger.exception("nightly_summary sweep failed")

    await _with_advisory_lock(
        _LOCK_NIGHTLY_SUMMARY, "nightly_summary_sweep", _impl
    )


# ── Booking reminders (Item 31 — v47) ────────────────────────────────────────


async def _dispatch_booking_reminders() -> None:
    """Send due appointment reminders (24h + 2h before start).

    Every 5 minutes each replica tries the advisory lock; the winner
    calls the dispatcher which pulls ``status='pending'`` rows whose
    ``scheduled_at <= now`` and delivers via WhatsApp/SMS. The lock plus
    the per-row status transition guarantee no double-sends.
    """
    async def _impl(db: AsyncSession) -> None:
        from app.services.booking_reminders import dispatch_due_reminders

        summary = await dispatch_due_reminders(db)
        if summary.get("sent") or summary.get("failed"):
            logger.info("booking reminders dispatched: %s", summary)

    await _with_advisory_lock(
        _LOCK_BOOKING_REMINDERS, "booking_reminders", _impl
    )


# ── Commission monthly run (Item 32 — v48) ───────────────────────────────────


async def _monthly_commission_sweep() -> None:
    """Create a ``commission_runs`` row per org for last month and bind entries.

    Runs on the 1st of each month at 02:00 Stockholm, early enough to
    beat the 06:00 auto-reorder rush and the 07:30 nightly-summary window.
    For every org with unassigned entries in last-month's window we insert
    an ``open`` run and re-link those entries to it. The owner then
    reviews and calls ``POST /runs/{id}/lock`` from the dashboard.
    """
    from datetime import date as _date
    from datetime import timedelta as _td
    from sqlalchemy import select as _select
    import uuid as _uuid

    async def _impl(db: AsyncSession) -> None:
        from app.models.commissions import CommissionEntry, CommissionRun

        today = _date.today()
        # Last month's range: [first_of_last, last_of_last]
        first_of_this = today.replace(day=1)
        last_of_last = first_of_this - _td(days=1)
        first_of_last = last_of_last.replace(day=1)

        # Group unassigned entries by org_id and create one run per org.
        unassigned = (
            await db.execute(
                _select(CommissionEntry).where(
                    CommissionEntry.run_id.is_(None),
                    CommissionEntry.created_at >= datetime(
                        first_of_last.year, first_of_last.month, first_of_last.day, tzinfo=timezone.utc
                    ),
                    CommissionEntry.created_at < datetime(
                        first_of_this.year, first_of_this.month, first_of_this.day, tzinfo=timezone.utc
                    ),
                )
            )
        ).scalars().all()
        by_org: dict = {}
        for e in unassigned:
            by_org.setdefault(e.org_id, []).append(e)

        for org_id, entries in by_org.items():
            run = CommissionRun(
                id=_uuid.uuid4(),
                org_id=org_id,
                period_start=first_of_last,
                period_end=last_of_last,
                status="open",
            )
            db.add(run)
            await db.flush()
            for entry in entries:
                entry.run_id = run.id
            logger.info(
                "monthly commission run created | org=%s entries=%d period=%s..%s",
                org_id, len(entries), first_of_last, last_of_last,
            )
        await db.commit()

    await _with_advisory_lock(
        _LOCK_COMMISSION_MONTHLY, "commission_monthly", _impl
    )


async def _giftcard_expiry_sweep() -> None:
    """Daily sweep: notify customers whose gift cards expire soon.

    Scans every ``active`` card expiring in the next 7 days and
    emails the owner (when ``issued_to_customer_id`` is set and the
    customer has an email). Best-effort per card — one bad row must
    not stop the rest of the run. Cards that expired in the past are
    flipped to ``status='expired'`` so the POS balance check returns
    the right state even if no one ever asks after them.
    """
    async def _impl() -> None:
        from datetime import datetime as _dt, timedelta as _td, timezone as _tz

        from sqlalchemy import select as _select

        from app.database import AsyncSessionLocal
        from app.models.gift_cards import GiftCard
        from app.models.invoicing import Customer
        from app.models.organization import Organization
        from app.services.email import send_giftcard_expiry_email

        async with AsyncSessionLocal() as db:
            now = _dt.now(tz=_tz.utc)
            upcoming_cutoff = now + _td(days=7)

            # 1) Expire past-due cards so balance check is truthful.
            past_due = (
                await db.execute(
                    _select(GiftCard).where(
                        GiftCard.status == "active",
                        GiftCard.expires_at.is_not(None),
                        GiftCard.expires_at <= now,
                    )
                )
            ).scalars().all()
            for card in past_due:
                card.status = "expired"
            if past_due:
                logger.info("gift card expiry sweep: expired %d past-due cards", len(past_due))

            # 2) Notify owners of cards expiring in the next 7 days.
            soon = (
                await db.execute(
                    _select(GiftCard).where(
                        GiftCard.status == "active",
                        GiftCard.expires_at.is_not(None),
                        GiftCard.expires_at > now,
                        GiftCard.expires_at <= upcoming_cutoff,
                        GiftCard.issued_to_customer_id.is_not(None),
                    )
                )
            ).scalars().all()

            notified = 0
            for card in soon:
                try:
                    customer = await db.get(Customer, card.issued_to_customer_id)
                    if customer is None or not getattr(customer, "email", None):
                        continue
                    org = await db.get(Organization, card.org_id)
                    org_name = getattr(org, "name", "") if org else ""
                    await send_giftcard_expiry_email(
                        to_email=customer.email,
                        giftcard_code=card.code,
                        remaining_value=str(card.remaining_value),
                        expire_date=card.expires_at.date().isoformat(),
                        org_name=org_name,
                    )
                    notified += 1
                except Exception:
                    logger.exception("gift card expiry notify failed | card=%s", card.id)
            if notified:
                logger.info("gift card expiry sweep: notified %d customers", notified)
            await db.commit()

    await _with_advisory_lock(
        _LOCK_GIFTCARD_EXPIRY, "giftcard_expiry", _impl
    )


async def _exchange_rate_sweep() -> None:
    """Daily fetch of fiat exchange rates into ``exchange_rates``.

    Runs once per distinct base currency across all orgs so a
    tenant with ``base_currency='EUR'`` gets EUR-based rates and a
    tenant with ``base_currency='SEK'`` gets SEK-based ones. Empty
    fetches (no API key, network blip) are no-ops — existing
    transactions continue to work at their snapshot rates.
    """
    async def _impl() -> None:
        from sqlalchemy import select as _select

        from app.database import AsyncSessionLocal
        from app.models.organization import Organization
        from app.services.currency import fetch_exchange_rates, store_rates

        async with AsyncSessionLocal() as db:
            bases = (
                await db.execute(
                    _select(Organization.base_currency).distinct()
                )
            ).scalars().all()
            bases = {b for b in bases if b}
            if not bases:
                bases = {"SEK"}
            total_written = 0
            for base in sorted(bases):
                rates = await fetch_exchange_rates(base)
                if not rates:
                    continue
                total_written += await store_rates(db, rates=rates)
            if total_written:
                logger.info("exchange rate sweep: wrote %d rows across %d bases", total_written, len(bases))
            await db.commit()

    await _with_advisory_lock(
        _LOCK_EXCHANGE_RATES, "exchange_rates", _impl
    )


async def _loyalty_expiry_sweep() -> None:
    """Daily sweep that expires stale loyalty points (Item 35).

    Two passes per invocation:

    1. ``expire_old_points`` — turns every overdue ``earn`` row into
       a matching negative ``expire`` ledger row and decrements the
       account balance. Idempotent; the WHERE clause excludes rows
       that have already been neutralised.
    2. ``points_expiring_soon`` — queues a heads-up notification so
       customers see the "{n} points expire on {date}" banner in the
       customer app. Best-effort notifications never block the sweep.
    """
    async def _impl() -> None:
        from app.database import AsyncSessionLocal
        from app.services.loyalty_engine import (
            expire_old_points,
            points_expiring_soon,
        )

        async with AsyncSessionLocal() as db:
            touched = await expire_old_points(db)
            soon = await points_expiring_soon(db, within_days=14)
            if touched:
                logger.info("loyalty expiry sweep: expired points on %d accounts", touched)
            if soon:
                logger.info(
                    "loyalty expiry sweep: %d accounts have points expiring within 14d",
                    len(soon),
                )
            await db.commit()

    await _with_advisory_lock(
        _LOCK_LOYALTY_EXPIRY, "loyalty_expiry", _impl
    )


async def _segment_refresh_sweep() -> None:
    """Nightly refresh of every AUTO customer segment (Item 39).

    Iterates organisations that have at least one AUTO segment and
    recomputes their membership via the shared metrics roll-up. A
    single advisory lock guards the sweep so two replicas cannot
    replay the delete+insert transaction for the same org.
    """
    async def _impl(db: AsyncSession) -> None:
        from app.models.segments import Segment, SegmentType

        # Scope to orgs with AUTO segments so a tenant with no
        # segments pays zero per-night cost.
        org_rows = (
            await db.execute(
                select(Segment.org_id)
                .where(Segment.type == SegmentType.AUTO)
                .distinct()
            )
        ).all()
        if not org_rows:
            return

        from app.services.segmentation_engine import refresh_all_auto_segments

        for (oid,) in org_rows:
            try:
                total = await refresh_all_auto_segments(db, org_id=oid)
                await db.commit()
                logger.info(
                    "segment_refresh org=%s members=%d", oid, total,
                )
            except Exception:
                await db.rollback()
                logger.exception("segment_refresh failed org=%s", oid)

    await _with_advisory_lock(
        _LOCK_SEGMENT_REFRESH, "segment_refresh", _impl,
    )


async def _campaign_dispatch_sweep() -> None:
    """Dispatch every SCHEDULED campaign whose ``scheduled_at <= now`` (Item 40).

    The campaign_engine processes each due campaign inside its own
    commit, so a bad payload in one campaign (e.g. the segment was
    deleted) cannot block the queue behind it. Runs every 5 minutes
    so a campaign scheduled for e.g. 09:00 Mon arrives at most 5 min
    after the wall clock — same tolerance as the booking-reminders
    sweep.
    """
    async def _impl(db: AsyncSession) -> None:
        from app.services.campaign_engine import process_due_campaigns

        sent = await process_due_campaigns(db)
        if sent:
            logger.info("campaign_dispatch sent=%d", len(sent))

    await _with_advisory_lock(
        _LOCK_CAMPAIGN_DISPATCH, "campaign_dispatch", _impl,
    )


async def _review_request_sweep() -> None:
    """Fire review-request magic links for bookings completed in the
    last 24h that don't yet have a request (Item 49).

    Acts as a safety net — the status endpoint already creates a
    request inline on completion, but this sweep catches rows that
    slipped through (e.g. status transitions performed by direct SQL
    during an import, or an older booking that was backfilled).
    """
    from datetime import timedelta

    async def _impl(db: AsyncSession) -> None:
        from app.models.bookings import Appointment
        from app.models.reviews import ReviewRequest
        from app.services.review_dispatch import maybe_create_review_request

        cutoff = datetime.now(timezone.utc) - timedelta(days=1)
        # Completed bookings from the last 24h with a customer attached.
        result = await db.execute(
            select(Appointment).where(
                Appointment.status == "completed",
                Appointment.customer_id.isnot(None),
                Appointment.updated_at >= cutoff,
            )
        )
        appts = result.scalars().all()
        created = 0
        for appt in appts:
            try:
                rr = await maybe_create_review_request(
                    db,
                    org_id=appt.org_id,
                    customer_id=appt.customer_id,
                    source_type="booking",
                    source_id=appt.id,
                )
                if rr is not None:
                    created += 1
            except Exception:
                logger.exception("review_request_sweep: failed for appt %s", appt.id)
        if created:
            await db.commit()
            logger.info("review_request_sweep created=%d", created)

    await _with_advisory_lock(
        _LOCK_REVIEW_REQUEST_SWEEP, "review_request_sweep", _impl,
    )


async def _subscription_pause_sweep() -> None:
    """Item 50 — daily sweep across paused orgs.

    Two duties in one job so the advisory lock and session overhead
    don't pay twice:

    * Auto-resume orgs whose ``pause_ends_at`` has elapsed (manual
      resume can also happen via the router, so this is the safety
      net for orgs the operator never came back to).
    * Send the 7-day-before reminder email exactly once per pause
      window, guarded by ``pause_reminder_sent_at``.
    """
    async def _impl(db: AsyncSession) -> None:
        from app.models.organization import Organization, SubscriptionPause
        from app.services import subscription_pause as pause_svc
        from app.services.email import send_subscription_pause_reminder_email

        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(Organization).where(Organization.is_paused.is_(True))
        )
        orgs = result.scalars().all()
        resumed = 0
        reminded = 0
        for org in orgs:
            try:
                if org.pause_ends_at is None:
                    continue

                # Auto-resume if past the window.
                if pause_svc.should_auto_resume(org.pause_ends_at, now=now):
                    # Close the open history row.
                    existing = (
                        await db.execute(
                            select(SubscriptionPause).where(
                                SubscriptionPause.org_id == org.id,
                                SubscriptionPause.ended_at.is_(None),
                            )
                        )
                    ).scalar_one_or_none()
                    if existing is not None:
                        existing.ended_at = now
                        existing.resume_reason = "auto_resume"
                    org.is_paused = False
                    org.paused_at = None
                    org.pause_ends_at = None
                    org.pause_reminder_sent_at = None
                    resumed += 1
                    continue

                # Reminder due?
                if pause_svc.is_reminder_due(
                    org.pause_ends_at,
                    org.pause_reminder_sent_at,
                    now=now,
                ):
                    # Fire-and-forget email — mailer already handles
                    # its own errors and returns False on failure.
                    notify = org.auto_reorder_notify_email or None
                    if notify:
                        try:
                            await send_subscription_pause_reminder_email(
                                notify, org.name, org.pause_ends_at.date().isoformat()
                            )
                        except Exception:
                            logger.exception(
                                "subscription_pause_reminder: email failed for %s",
                                org.id,
                            )
                    org.pause_reminder_sent_at = now
                    reminded += 1
            except Exception:
                logger.exception(
                    "subscription_pause_sweep: failed for org %s", org.id
                )
        if resumed or reminded:
            await db.commit()
            logger.info(
                "subscription_pause_sweep resumed=%d reminded=%d",
                resumed, reminded,
            )

    await _with_advisory_lock(
        _LOCK_SUBSCRIPTION_PAUSE_SWEEP, "subscription_pause_sweep", _impl,
    )


# ── Abandoned cart recovery (E-commerce) ─────────────────────────────────────


async def _abandoned_cart_sweep() -> None:
    """Every 15 min: find guest carts inactive >1h with an email and send recovery.

    Uses the shared advisory lock so only one Railway replica sends per window.
    The cart_recovery service sets ``abandoned_email_sent_at`` on each sent cart
    so this job is naturally idempotent — re-running never double-sends.
    """
    async def _impl(db: AsyncSession) -> None:
        from app.services.cart_recovery import send_abandoned_cart_emails

        try:
            sent = await send_abandoned_cart_emails(db)
            if sent:
                logger.info("abandoned_cart_sweep sent=%d", sent)
        except Exception:
            logger.exception("abandoned_cart_sweep failed")

    await _with_advisory_lock(
        _LOCK_ABANDONED_CART, "abandoned_cart_sweep", _impl,
    )


async def _email_sequence_drip_sweep() -> None:
    """Every hour: send due drip steps and enroll new segment members."""
    async def _impl(db: AsyncSession) -> None:
        from app.services.email_sequence_engine import (
            send_due_steps,
            enroll_segment_sequences,
        )

        try:
            sent = await send_due_steps(db)
            enrolled = await enroll_segment_sequences(db)
            if sent or enrolled:
                logger.info("email_sequence_drip sent=%d enrolled=%d", sent, enrolled)
        except Exception:
            logger.exception("email_sequence_drip_sweep failed")

    await _with_advisory_lock(
        _LOCK_EMAIL_SEQUENCE_DRIP, "email_sequence_drip_sweep", _impl,
    )


async def _quote_expiry_sweep() -> None:
    """Nightly: flip quotes past valid_until from sent/viewed → expired."""
    async def _impl(db: AsyncSession) -> None:
        from app.models.quotes import Quote
        from datetime import date as _date, datetime as _dt, timezone as _tz
        try:
            today = _date.today()
            rows = (await db.execute(
                select(Quote).where(
                    Quote.valid_until < today,
                    Quote.status.in_(["sent", "viewed"]),
                )
            )).scalars().all()
            if rows:
                now = _dt.now(_tz.utc)
                for q in rows:
                    q.status = "expired"
                    q.updated_at = now
                await db.commit()
                logger.info("quote_expiry_sweep expired=%d", len(rows))
        except Exception:
            logger.exception("quote_expiry_sweep failed")

    await _with_advisory_lock(_LOCK_QUOTE_EXPIRY, "quote_expiry_sweep", _impl)


async def _trial_sweep() -> None:
    """
    Daily at 02:00 Stockholm:
    - Day 13: send 1-day-before reminder
    - Day 15 (grace +1): auto-downgrade to FREE and send expired email
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.models.idempotency import IdempotencyKey
    from app.models.organization import OrgPlan, Organization
    from app.services import trial_service as svc
    from app.services.email import send_trial_ended_soon_email, send_trial_expired_email

    async def _impl(db: AsyncSession) -> None:
        try:
            now = datetime.now(timezone.utc)
            result = await db.execute(
                select(Organization).where(
                    Organization.trial_ends_at.isnot(None),
                    Organization.trial_converted_at.is_(None),
                )
            )
            orgs = list(result.scalars().all())
            reminded = 0
            expired = 0
            for org in orgs:
                if org.trial_ends_at is None:
                    continue
                delta = org.trial_ends_at - now
                days_left = delta.days

                # Day-13 reminder (fire when 1 day remains)
                if days_left == 1:
                    slot = await db.execute(
                        pg_insert(IdempotencyKey.__table__)
                        .values(
                            org_id=org.id,
                            endpoint="scheduler.trial_reminder",
                            key=f"trial_reminder:{org.trial_ends_at.date()}",
                            target_id=str(org.id),
                        )
                        .on_conflict_do_nothing(index_elements=["org_id", "endpoint", "key"])
                    )
                    if slot.rowcount == 0:
                        continue
                    await db.commit()
                    try:
                        from app.services.email import send_trial_ending_soon_email
                        owner_email = getattr(org, "orders_notification_email", None)
                        if owner_email:
                            await send_trial_ending_soon_email(
                                to_email=owner_email,
                                org_name=org.name,
                                plan=org.trial_plan or "PRO",
                                trial_ends_at=org.trial_ends_at,
                                days_remaining=1,
                            )
                    except Exception:
                        logger.exception("trial_reminder email failed org=%s", org.id)
                    reminded += 1

                # Day 15 — grace expired, downgrade
                elif days_left <= -(svc.GRACE_PERIOD_DAYS):
                    slot = await db.execute(
                        pg_insert(IdempotencyKey.__table__)
                        .values(
                            org_id=org.id,
                            endpoint="scheduler.trial_expire",
                            key=f"trial_expire:{org.trial_ends_at.date()}",
                            target_id=str(org.id),
                        )
                        .on_conflict_do_nothing(index_elements=["org_id", "endpoint", "key"])
                    )
                    if slot.rowcount == 0:
                        continue
                    await db.commit()
                    await svc.expire_trial(org, db)
                    from app.services.audit import log_action
                    await log_action(
                        db,
                        action="trial.expired",
                        org_id=org.id,
                        target_type="organization",
                        target_id=str(org.id),
                    )
                    await db.commit()
                    try:
                        owner_email = getattr(org, "orders_notification_email", None)
                        if owner_email:
                            await send_trial_expired_email(
                                to_email=owner_email,
                                org_name=org.name,
                                plan=org.trial_plan or "PRO",
                            )
                    except Exception:
                        logger.exception("trial_expired email failed org=%s", org.id)
                    expired += 1

            logger.info("trial_sweep reminded=%d expired=%d", reminded, expired)
        except Exception:
            logger.exception("trial_sweep failed")

    await _with_advisory_lock(_LOCK_TRIAL_SWEEP, "trial_sweep", _impl)


# ── Public API ────────────────────────────────────────────────────────────────

async def _partner_commissions_sweep() -> None:
    """Monthly on 1st at 03:30 Stockholm — decrement months_remaining for all
    active accounting-firm-partner and operator referrals, marking paid_out
    when the 12-month window closes.
    """
    from app.services.partner_commissions import (
        process_monthly_accounting_commissions,
        process_monthly_operator_commissions,
    )

    async def _impl(db: AsyncSession) -> None:
        try:
            count_acct = await process_monthly_accounting_commissions(db)
            count_ops = await process_monthly_operator_commissions(db)
            logger.info(
                "partner_commissions_sweep completed",
                extra={"accounting_referrals": count_acct, "operator_referrals": count_ops},
            )
        except Exception as exc:
            logger.error(f"partner_commissions_sweep failed: {exc}")

    await _with_advisory_lock(_LOCK_PARTNER_COMMISSIONS, "partner_commissions_sweep", _impl)


async def _health_score_sweep() -> None:
    """Weekly Monday 04:00 Stockholm — calculate health scores for all paying orgs.

    Triggers interventions:
    - at_risk: send check-in email
    - critical: send urgent founder email + Slack notification
    """
    from app.models.organization import Organization, OrgPlan
    from app.services.subscription_health import HealthFactors, calculate_health_score, save_health_score
    from app.services.nps import get_org_nps
    from app.services.email import (
        send_nps_at_risk_checkin_email,
        send_nps_critical_intervention_email,
    )
    from app.services.subscription_health import mark_intervention

    _CSM_NAME = "Varuflow Customer Success"
    _CSM_CALENDLY = getattr(settings, "CALENDLY_CSM_URL", "https://calendly.com/varuflow/success")
    _FOUNDER_NAME = "Marcus Berg"
    _FOUNDER_EMAIL = "marcus@varuflow.app"
    _FOUNDER_CALENDLY = getattr(settings, "CALENDLY_FOUNDER_URL", "https://calendly.com/varuflow/founders")

    async def _impl(db: AsyncSession) -> None:
        try:
            # Fetch all paying orgs (not free/trial)
            result = await db.execute(
                select(Organization).where(
                    Organization.plan.in_([OrgPlan.STARTER, OrgPlan.PRO, OrgPlan.ENTERPRISE])
                    if hasattr(OrgPlan, 'STARTER') else
                    select(Organization)
                )
            )
            orgs = list(result.scalars().all())
            healthy = at_risk = critical = 0
            for org in orgs:
                try:
                    # Build factors from org attributes — real implementation
                    # would JOIN activity tables; this uses available org fields
                    nps_data = await get_org_nps(db, org.id, days=90)
                    last_nps = None
                    if nps_data["total"] > 0:
                        last_nps = round((nps_data["nps_score"] + 100) / 10)  # remap to 0-10

                    factors = HealthFactors(
                        onboarding_complete=getattr(org, "onboarding_complete", False),
                        last_nps_score=last_nps,
                    )
                    score_obj = await save_health_score(db, org.id, factors)
                    if score_obj.risk_level == "healthy":
                        healthy += 1
                    elif score_obj.risk_level == "at_risk":
                        at_risk += 1
                        # Send check-in only if no intervention has fired yet
                        if score_obj.intervention_triggered_at is None:
                            to_email = await _org_notification_email(db, org.id)
                            if to_email:
                                sent = await send_nps_at_risk_checkin_email(
                                    to_email=to_email,
                                    org_name=getattr(org, "name", str(org.id)),
                                    health_score=score_obj.score,
                                    csm_name=_CSM_NAME,
                                    csm_calendly_url=_CSM_CALENDLY,
                                )
                                if sent:
                                    await mark_intervention(db, score_id=score_obj.id)
                    else:
                        critical += 1
                        # Send founder email only if no intervention has fired yet
                        if score_obj.intervention_triggered_at is None:
                            to_email = await _org_notification_email(db, org.id)
                            if to_email:
                                sent = await send_nps_critical_intervention_email(
                                    to_email=to_email,
                                    org_name=getattr(org, "name", str(org.id)),
                                    health_score=score_obj.score,
                                    founder_name=_FOUNDER_NAME,
                                    founder_email=_FOUNDER_EMAIL,
                                    founder_calendly_url=_FOUNDER_CALENDLY,
                                )
                                if sent:
                                    await mark_intervention(db, score_id=score_obj.id)
                except Exception as exc:
                    logger.warning(f"health_score_sweep: failed for org {org.id}: {exc}")
            logger.info(
                "health_score_sweep completed",
                extra={"healthy": healthy, "at_risk": at_risk, "critical": critical},
            )
        except Exception as exc:
            logger.error(f"_health_score_sweep failed: {exc}")

    await _with_advisory_lock(_LOCK_NPS_HEALTH, "health_score_sweep", _impl)


async def _nps_reminder_sweep() -> None:
    """Daily 10:00 Stockholm — send 24h follow-up to users who haven't responded.

    Finds NPS surveys triggered 24-48 hours ago with no response and
    followup_status != 'reminded', sends the reminder email, then sets
    followup_status = 'reminded' so it fires at most once per survey.
    """
    from app.models.nps import NpsSurvey
    from app.models.organization import Organization
    from app.services.email import send_nps_survey_email

    async def _impl(db: AsyncSession) -> None:
        try:
            now = datetime.now(timezone.utc)
            window_start = now - timedelta(hours=48)
            window_end = now - timedelta(hours=24)
            result = await db.execute(
                select(NpsSurvey).where(
                    NpsSurvey.triggered_at >= window_start,
                    NpsSurvey.triggered_at <= window_end,
                    NpsSurvey.responded_at.is_(None),
                    NpsSurvey.followup_status != "reminded",
                )
            )
            surveys = result.scalars().all()
            sent = skipped = 0
            for survey in surveys:
                try:
                    to_email = await _org_notification_email(db, survey.org_id)
                    if not to_email:
                        skipped += 1
                        continue
                    org = await db.get(Organization, survey.org_id)
                    org_name = getattr(org, "name", str(survey.org_id)) if org else str(survey.org_id)
                    frontend_url = getattr(settings, "FRONTEND_URL", "https://varuflow.vercel.app")
                    survey_url = f"{frontend_url}/en/dashboard?nps=1"
                    ok = await send_nps_survey_email(
                        to_email=to_email,
                        org_name=org_name,
                        survey_url=survey_url,
                    )
                    if ok:
                        survey.followup_status = "reminded"
                        sent += 1
                    else:
                        skipped += 1
                except Exception as exc:
                    logger.warning(f"nps_reminder_sweep: survey {survey.id} failed: {exc}")
                    skipped += 1
            await db.commit()
            logger.info(
                "nps_reminder_sweep completed",
                extra={"sent": sent, "skipped": skipped},
            )
        except Exception as exc:
            logger.error(f"_nps_reminder_sweep failed: {exc}")

    await _with_advisory_lock(_LOCK_NPS_REMINDER, "nps_reminder_sweep", _impl)


async def _trial_onboarding_sweep() -> None:
    """Hourly — send due trial onboarding emails."""
    from app.services.trial_sequences import process_pending_sends

    async def _impl(db: AsyncSession) -> None:
        try:
            sent = await process_pending_sends(db)
            logger.info("trial_onboarding_sweep", extra={"sent": sent})
        except Exception as exc:
            logger.error(f"trial_onboarding_sweep failed: {exc}")

    await _with_advisory_lock(_LOCK_TRIAL_ONBOARDING, "trial_onboarding_sweep", _impl)


def create_scheduler() -> AsyncIOScheduler:
    """Build and return a configured AsyncIOScheduler (not yet started)."""
    scheduler = AsyncIOScheduler(timezone="Europe/Stockholm")

    # Fortnox: every 15 minutes
    scheduler.add_job(
        _sync_fortnox,
        trigger=IntervalTrigger(minutes=15),
        id="fortnox_sync",
        replace_existing=True,
        misfire_grace_time=120,
    )

    # Low-stock alerts: daily at 08:00 Stockholm
    scheduler.add_job(
        _check_low_stock,
        trigger=CronTrigger(hour=8, minute=0, timezone="Europe/Stockholm"),
        id="low_stock_check",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Weekly digest: Monday 08:00 Stockholm
    scheduler.add_job(
        _send_weekly_digest,
        trigger=CronTrigger(day_of_week="mon", hour=8, minute=0, timezone="Europe/Stockholm"),
        id="weekly_digest",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Stale-token cleanup: daily at 03:00 Stockholm (low-traffic window)
    scheduler.add_job(
        _cleanup_stale_tokens,
        trigger=CronTrigger(hour=3, minute=0, timezone="Europe/Stockholm"),
        id="token_cleanup",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Bokföring compliance reminder: once a year on Jan 15 08:00 Stockholm
    scheduler.add_job(
        _bokforing_reminder,
        trigger=CronTrigger(month=1, day=15, hour=8, minute=0, timezone="Europe/Stockholm"),
        id="bokforing_reminder",
        replace_existing=True,
        misfire_grace_time=86400,  # if the replica was down Jan 15, still send by Jan 16
    )

    # Dunning sweep: daily at 09:00 Stockholm (after daily digest window,
    # before Swedish business hours so customers see the reminder early).
    scheduler.add_job(
        _run_dunning,
        trigger=CronTrigger(hour=9, minute=0, timezone="Europe/Stockholm"),
        id="dunning_sweep",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Push: stockout-imminent — daily at 07:55 Stockholm, runs just
    # before the low-stock email so both signals use the same dedupe
    # window but mobile users see it first.
    scheduler.add_job(
        _push_stockout_imminent,
        trigger=CronTrigger(hour=7, minute=55, timezone="Europe/Stockholm"),
        id="push_stockout",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Push: overdue D+1 — daily at 08:10 Stockholm, fills the 2-day gap
    # between due_date and dunning stage 1 (D+3).
    scheduler.add_job(
        _push_overdue_invoices,
        trigger=CronTrigger(hour=8, minute=10, timezone="Europe/Stockholm"),
        id="push_overdue",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Onboarding reminder — daily at 09:30 Stockholm. Emails orgs that
    # registered >48h ago with zero checklist progress. One-shot per org
    # via IdempotencyKey.
    scheduler.add_job(
        _send_onboarding_reminder,
        trigger=CronTrigger(hour=9, minute=30, timezone="Europe/Stockholm"),
        id="onboarding_reminder",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Webhook retry sweep — every 5 minutes. The dispatcher writes the
    # next-retry timestamp using the exponential schedule (5m → 30m →
    # 2h → 12h → 24h); this job picks every row whose retry time has
    # arrived and re-attempts delivery.
    scheduler.add_job(
        _retry_webhooks,
        trigger=IntervalTrigger(minutes=5),
        id="webhook_retry",
        replace_existing=True,
        misfire_grace_time=600,
    )

    # Health probe — every 5 minutes. Powers the public /status page;
    # the row count drives uptime % over 90 days, so misfires would
    # leave gaps in the timeline. 5 min cadence matches the bucket
    # granularity callers expect from a Stripe-style status page.
    scheduler.add_job(
        _run_health_probe,
        trigger=IntervalTrigger(minutes=5),
        id="health_probe",
        replace_existing=True,
        misfire_grace_time=600,
    )

    # Stuck stock-count sweep — hourly. Clients are expected to finish
    # /submit → /sync within minutes, so rows stranded >24h in SUBMITTED
    # get reset to DRAFT for the next reconnect to retry.
    scheduler.add_job(
        _check_stuck_stock_counts,
        trigger=IntervalTrigger(hours=1),
        id="stock_count_stuck",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Auto-reorder sweep — daily at 06:00 Stockholm. Per-org schedule
    # is enforced inside the job (day-of-week + ``auto_reorder_enabled``)
    # so a single cron tick covers every tenant. Six AM is quiet enough
    # that even a 500-tenant sweep completes before business hours but
    # the draft-POs email lands in the owner's inbox at their desk.
    scheduler.add_job(
        _auto_reorder_check,
        trigger=CronTrigger(hour=6, minute=0, timezone="Europe/Stockholm"),
        id="auto_reorder_check",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Recurring invoice auto-send — daily at 07:00 Stockholm. Runs an
    # hour after auto-reorder so invoice emails do not land in the same
    # inbox batch as supplier PO emails, and before the 08:00 low-stock
    # email so the owner sees billing activity before inventory alerts.
    scheduler.add_job(
        _recurring_autosend,
        trigger=CronTrigger(hour=7, minute=0, timezone="Europe/Stockholm"),
        id="recurring_autosend",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Nightly business summary — every 15 min (Europe/Stockholm). The
    # sweep itself filters to orgs whose configured send time falls in
    # the current 15-min window, so a single cron gang covers every
    # tenant regardless of their preferred delivery time. Idempotency
    # via audit-log probe protects against scheduler misfires.
    scheduler.add_job(
        _nightly_summary_sweep,
        trigger=CronTrigger(minute="*/15", timezone="Europe/Stockholm"),
        id="nightly_summary_sweep",
        replace_existing=True,
        misfire_grace_time=900,
    )

    # Booking reminders — every 5 min. The dispatcher filters to rows
    # whose scheduled_at is in the past, so a single interval job
    # covers both 24h-before and 2h-before deliveries. Short cadence
    # keeps the 2h reminder's drift < 5 min; longer would risk a
    # reminder landing during (not before) the appointment.
    scheduler.add_job(
        _dispatch_booking_reminders,
        trigger=IntervalTrigger(minutes=5),
        id="booking_reminders",
        replace_existing=True,
        misfire_grace_time=600,
    )

    # Monthly commission run sweep — 1st of the month, 02:00 Stockholm.
    # Early enough to beat the 06:00 auto-reorder rush and the 07:30
    # nightly-summary window; late enough that any end-of-month bookings
    # that landed just before midnight have been fully written.
    scheduler.add_job(
        _monthly_commission_sweep,
        trigger=CronTrigger(day=1, hour=2, minute=0, timezone="Europe/Stockholm"),
        id="commission_monthly",
        replace_existing=True,
        misfire_grace_time=86400,  # tolerate an 24h slip without re-running twice
    )

    # Gift-card expiry sweep — daily at 09:00 Stockholm. Runs after
    # the morning operator shift starts so notifications land in
    # inboxes while customers are active. Misfire grace of 12h keeps
    # the daily cadence even if the dyno restarts mid-morning.
    scheduler.add_job(
        _giftcard_expiry_sweep,
        trigger=CronTrigger(hour=9, minute=0, timezone="Europe/Stockholm"),
        id="giftcard_expiry",
        replace_existing=True,
        misfire_grace_time=43200,
    )

    # Exchange-rate sweep — daily at 06:00 Stockholm. Before the
    # 07:30 nightly-summary job so the summary emails see fresh rates.
    # Misfire grace 1h — a single slip re-runs at 07:00 rather than
    # stacking two sweeps the next morning.
    scheduler.add_job(
        _exchange_rate_sweep,
        trigger=CronTrigger(hour=6, minute=0, timezone="Europe/Stockholm"),
        id="exchange_rates",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Loyalty-points expiry sweep — daily at 03:00 Stockholm, before
    # the morning rate + low-stock + dunning jobs. Sits in a quiet
    # window to avoid contending with the 02:00 monthly commission
    # job on the first of the month. Misfire grace 12h.
    scheduler.add_job(
        _loyalty_expiry_sweep,
        trigger=CronTrigger(hour=3, minute=0, timezone="Europe/Stockholm"),
        id="loyalty_expiry",
        replace_existing=True,
        misfire_grace_time=43200,
    )

    # Segment refresh — nightly at 03:30 Stockholm. Runs after loyalty
    # expiry (03:00) so customers expired from the loyalty ledger this
    # cycle are re-evaluated with their new state. Misfire grace 12h
    # so a dyno restart mid-sweep still catches the run by 15:30 the
    # next day rather than stacking two sweeps tomorrow night.
    scheduler.add_job(
        _segment_refresh_sweep,
        trigger=CronTrigger(hour=3, minute=30, timezone="Europe/Stockholm"),
        id="segment_refresh",
        replace_existing=True,
        misfire_grace_time=43200,
    )

    # Campaign dispatch — every 5 minutes. The job filters to
    # ``status='SCHEDULED' AND scheduled_at <= now`` so a campaign
    # scheduled for wall-clock 09:00 fires between 09:00 and 09:05.
    # Shorter cadence would tighten the window but add scheduler
    # pressure; 5 min matches the booking-reminder cadence which has
    # a similar "fire shortly after" contract.
    scheduler.add_job(
        _campaign_dispatch_sweep,
        trigger=IntervalTrigger(minutes=5),
        id="campaign_dispatch",
        replace_existing=True,
        misfire_grace_time=600,
    )

    # Review-request sweep — nightly at 04:00 Stockholm (Item 49).
    # Safety net for bookings completed via code paths that bypass
    # the status endpoint. 04:00 keeps it clear of the 03:00 loyalty
    # expiry and 03:30 segment refresh windows.
    scheduler.add_job(
        _review_request_sweep,
        trigger=CronTrigger(hour=4, minute=0, timezone="Europe/Stockholm"),
        id="review_request_sweep",
        replace_existing=True,
        misfire_grace_time=43200,
    )

    # Subscription-pause sweep — daily at 10:00 Stockholm (Item 50).
    # Runs after the morning freshness jobs so auto-resume events
    # land on an already-warm app. Handles both the 7-day reminder
    # email and the auto-resume-at-90-days flow.
    scheduler.add_job(
        _subscription_pause_sweep,
        trigger=CronTrigger(hour=10, minute=0, timezone="Europe/Stockholm"),
        id="subscription_pause_sweep",
        replace_existing=True,
        misfire_grace_time=43200,
    )

    # Abandoned cart recovery — every 15 min. The job finds carts with a
    # captured email that have been idle >1h, not yet recovered and not yet
    # emailed. Runs on the same cadence as the nightly-summary sweep; the
    # advisory lock prevents concurrent replicas from double-sending.
    scheduler.add_job(
        _abandoned_cart_sweep,
        trigger=IntervalTrigger(minutes=15),
        id="abandoned_cart_sweep",
        replace_existing=True,
        misfire_grace_time=900,
    )

    # Email sequence drip: hourly step dispatch + segment auto-enroll.
    scheduler.add_job(
        _email_sequence_drip_sweep,
        trigger=IntervalTrigger(hours=1),
        id="email_sequence_drip_sweep",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    scheduler.add_job(
        _quote_expiry_sweep,
        trigger=CronTrigger(hour=2, minute=0),
        id="quote_expiry_sweep",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        _trial_sweep,
        trigger=CronTrigger(hour=2, minute=0, timezone="Europe/Stockholm"),
        id="trial_sweep",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Partner + operator commission monthly sweep — 1st of month at 03:30 Stockholm.
    # Runs after the 02:00 commission run so both are settled before business hours.
    scheduler.add_job(
        _partner_commissions_sweep,
        trigger=CronTrigger(day=1, hour=3, minute=30, timezone="Europe/Stockholm"),
        id="partner_commissions_sweep",
        replace_existing=True,
        misfire_grace_time=43200,  # 12h grace — monthly job
    )

    # Health score sweep — weekly Monday 04:00 Stockholm. Calculates subscription
    # health scores for all paying orgs and triggers proactive retention actions
    # for at_risk and critical orgs. 2h misfire grace covers most restart windows.
    scheduler.add_job(
        _health_score_sweep,
        trigger=CronTrigger(day_of_week="mon", hour=4, minute=0, timezone="Europe/Stockholm"),
        id="health_score_sweep",
        replace_existing=True,
        misfire_grace_time=7200,
    )

    # NPS 24h reminder sweep — daily 10:00 Stockholm. Sends one follow-up to
    # users who were shown an NPS survey but haven't responded within 24 hours.
    scheduler.add_job(
        _nps_reminder_sweep,
        trigger=CronTrigger(hour=10, minute=7, timezone="Europe/Stockholm"),
        id="nps_reminder_sweep",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Trial onboarding sweep — hourly. Sends due trial onboarding emails to
    # newly enrolled operator orgs. Advisory lock prevents double-sends across
    # Railway replicas.
    scheduler.add_job(
        _trial_onboarding_sweep,
        trigger=IntervalTrigger(hours=1, timezone="Europe/Stockholm"),
        id="trial_onboarding_sweep",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    return scheduler
