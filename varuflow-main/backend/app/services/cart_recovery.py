"""Abandoned cart recovery service.

Called by the scheduler every 15 minutes. Finds guest carts that:
  - Have at least one item
  - Have a customer email (captured at checkout form)
  - Were active more than 1 hour ago
  - Have not been recovered (order completed)
  - Have not already received a recovery email

Sends one recovery email per cart, then sets abandoned_email_sent_at.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.storefront.models import CartSession, Storefront

log = logging.getLogger(__name__)


async def send_abandoned_cart_emails(db: AsyncSession) -> int:
    """Send recovery emails for abandoned carts. Returns count of emails sent."""
    from app.services.email import send_abandoned_cart_recovery

    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    rows = (
        await db.execute(
            select(CartSession)
            .where(
                CartSession.customer_email.isnot(None),
                CartSession.recovered_at.is_(None),
                CartSession.abandoned_email_sent_at.is_(None),
                CartSession.last_activity_at < cutoff,
            )
        )
    ).scalars().all()

    sent = 0
    for cart in rows:
        # Skip empty carts
        if not cart.items:
            cart.abandoned_email_sent_at = datetime.now(timezone.utc)
            continue
        try:
            storefront = await db.get(Storefront, cart.storefront_id)
            if not storefront or not storefront.is_active:
                continue
            shop_url = f"/shop/{storefront.slug}/cart?token={cart.guest_token}"
            ok = await send_abandoned_cart_recovery(
                cart=cart,
                shop_url=shop_url,
                storefront_name=storefront.name,
            )
            if ok:
                cart.abandoned_email_sent_at = datetime.now(timezone.utc)
                sent += 1
        except Exception:
            log.exception("abandoned_cart email failed for cart %s", cart.id)

    await db.commit()
    return sent
