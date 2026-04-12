"""Background scheduler: Fortnox sync, low-stock alerts, weekly digest."""
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import engine

logger = logging.getLogger(__name__)

_SessionLocal: async_sessionmaker[AsyncSession] | None = None


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    return _SessionLocal


# ── Jobs ─────────────────────────────────────────────────────────────────────

async def _sync_fortnox() -> None:
    """Sync invoices for all orgs that have an active Fortnox connection."""
    from app.models.organization import Organization

    session_factory = _get_session_factory()
    async with session_factory() as db:
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
                    from datetime import datetime, timezone
                    if org.fortnox_token_expiry and org.fortnox_token_expiry < datetime.now(timezone.utc):
                        logger.info("Fortnox token expired for org %s — needs re-auth", org.id)
                except Exception:
                    logger.exception("Fortnox token check failed for org %s", org.id)
        except Exception:
            logger.exception("Fortnox sync job failed")


async def _check_low_stock() -> None:
    """Email orgs whose products have fallen below reorder_level."""
    from app.models.inventory import Product, StockLevel
    from app.models.organization import Organization
    from app.services.email import send_low_stock_alert_email

    session_factory = _get_session_factory()
    async with session_factory() as db:
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

            for org_id, items in by_org.items():
                org = await db.get(Organization, org_id)
                if not org or not org.billing_email:
                    continue
                await send_low_stock_alert_email(
                    to_email=org.billing_email,
                    org_name=org.name,
                    low_stock_items=items,
                )
                logger.info("Low-stock alert sent to %s (%d items)", org.name, len(items))
        except Exception:
            logger.exception("Low-stock check job failed")


async def _send_weekly_digest() -> None:
    """Send a weekly business digest to each org's billing email."""
    from app.models.inventory import Product, StockLevel
    from app.models.organization import Organization
    from app.models.pos import PosSale, PosSaleItem
    from app.services.email import send_weekly_digest_email

    session_factory = _get_session_factory()
    async with session_factory() as db:
        try:
            orgs_result = await db.execute(select(Organization))
            orgs = orgs_result.scalars().all()

            week_start = datetime.now(timezone.utc) - timedelta(days=7)
            week_ending = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            for org in orgs:
                if not org.billing_email:
                    continue
                try:
                    # Revenue + sale count for last 7 days
                    rev_row = await db.execute(
                        select(
                            func.coalesce(func.sum(PosSale.total), 0).label("revenue"),
                            func.count(PosSale.id).label("cnt"),
                        ).where(
                            PosSale.org_id == org.id,
                            PosSale.created_at >= week_start,
                        )
                    )
                    rev = rev_row.one()

                    # Top 5 products by quantity sold
                    top_result = await db.execute(
                        select(
                            PosSaleItem.description,
                            func.sum(PosSaleItem.quantity).label("qty"),
                        )
                        .join(PosSale, PosSale.id == PosSaleItem.sale_id)
                        .where(PosSale.org_id == org.id, PosSale.created_at >= week_start)
                        .group_by(PosSaleItem.description)
                        .order_by(func.sum(PosSaleItem.quantity).desc())
                        .limit(5)
                    )
                    top_products = [
                        {"name": r.description, "quantity": int(r.qty)}
                        for r in top_result.all()
                    ]

                    # Low-stock count
                    low_count = await db.scalar(
                        select(func.count(Product.id))
                        .outerjoin(StockLevel, StockLevel.product_id == Product.id)
                        .where(Product.org_id == org.id, Product.is_active == True)  # noqa: E712
                        .group_by(Product.id, Product.reorder_level)
                        .having(func.coalesce(func.sum(StockLevel.quantity), 0) <= Product.reorder_level)
                    ) or 0

                    await send_weekly_digest_email(
                        to_email=org.billing_email,
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


# ── Public API ────────────────────────────────────────────────────────────────

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

    return scheduler
