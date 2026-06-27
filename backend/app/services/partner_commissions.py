"""Pure helpers for accounting partner and operator referral commissions.

All functions are stateless and have zero ORM / network dependencies so
they can be exercised in unit tests without a running database.

Commission model
----------------
* Partners earn ``commission_rate_pct`` % of the monthly subscription for
  each active referral, for up to 12 calendar months after conversion.
* Month numbering starts at 1 (month of first charged invoice = month 1).
  Month 0 or negative = invalid → zero commission.
  Month 13+ = window expired → zero commission.
* Operator referrals follow the same arithmetic but typically use a 20%
  rate instead of the 25% default for accounting partners.
"""
from __future__ import annotations

import re
import secrets
import string
from decimal import ROUND_HALF_UP, Decimal

_TWO_PLACES = Decimal("0.01")

# Characters used in generated codes — no ambiguous glyphs (0/O, 1/I/L)
_ALPHA = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

COMMISSION_WINDOW_MONTHS: int = 12


# ── Core arithmetic ────────────────────────────────────────────────────────


def _q(value) -> Decimal:
    """Round to two decimal places, half-up."""
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def calculate_commission(
    subscription_amount,
    commission_rate_pct,
    month_number: int,
) -> Decimal:
    """Return the commission amount for a single month.

    Parameters
    ----------
    subscription_amount:
        The billed amount for the month (e.g. 500 SEK). Accepts ``int``,
        ``float``, or ``Decimal``.
    commission_rate_pct:
        Commission percentage as a plain number (25 → 25 %, not 0.25).
    month_number:
        1-indexed month within the commission window. Values ≤ 0 or > 12
        yield ``Decimal("0.00")``.
    """
    if month_number <= 0 or month_number > COMMISSION_WINDOW_MONTHS:
        return Decimal("0.00")
    base = Decimal(str(subscription_amount or 0))
    rate = Decimal(str(commission_rate_pct or 0))
    if base <= 0 or rate <= 0:
        return Decimal("0.00")
    return _q(base * rate / Decimal(100))


def is_commission_window_active(month_number: int) -> bool:
    """Return True when ``month_number`` falls within the 12-month window.

    Month 0, negative values, and months > 12 return False.
    """
    return 1 <= month_number <= COMMISSION_WINDOW_MONTHS


def calculate_free_month_value(subscription_amount) -> Decimal:
    """Return the monetary value of a free-month reward.

    For a free-month reward the value equals the subscription amount itself
    (the referred org's first charged invoice is waived).
    """
    return _q(Decimal(str(subscription_amount or 0)))


# ── Code generation ────────────────────────────────────────────────────────

_MAX_CODE_LEN = 20
_MAX_REF_LEN = 15

# Strip everything that is not a letter or digit, then upper-case.
_SLUG_RE = re.compile(r"[^A-Za-z0-9]+")


def _slugify(name: str, max_chars: int) -> str:
    """Return an upper-case, non-empty slug derived from *name*."""
    slug = _SLUG_RE.sub("", name).upper()[:max_chars]
    return slug or "X"


def generate_partner_code(firm_name: str) -> str:
    """Return a unique-enough partner referral code for an accounting firm.

    Format: ``PARTNER-<slug><random>`` where the total length is at most
    20 characters.  Callers that need true global uniqueness should check
    against the DB and regenerate on collision — but the random suffix
    makes that extremely unlikely.
    """
    prefix = "PARTNER-"
    remaining = _MAX_CODE_LEN - len(prefix)
    # Reserve 4 chars for random suffix
    slug_max = max(1, remaining - 4)
    slug = _slugify(firm_name, slug_max)
    random_suffix = "".join(secrets.choice(_ALPHA) for _ in range(4))
    code = f"{prefix}{slug}{random_suffix}"
    return code[:_MAX_CODE_LEN]


def generate_operator_referral_code(org_name: str) -> str:
    """Return a unique-enough referral code for an operator (SaaS user).

    Format: ``REF-<slug><random>`` where the total length is at most
    15 characters. No spaces are included.
    """
    prefix = "REF-"
    remaining = _MAX_REF_LEN - len(prefix)
    # Reserve 4 chars for random suffix
    slug_max = max(1, remaining - 4)
    slug = _slugify(org_name, slug_max) if org_name else ""
    random_suffix = "".join(secrets.choice(_ALPHA) for _ in range(4))
    code = f"{prefix}{slug}{random_suffix}"
    return code[:_MAX_REF_LEN]


# ── DB-bound async helpers ─────────────────────────────────────────────────

import logging as _logging
import uuid as _uuid
from datetime import datetime as _datetime, timezone as _timezone

_log = _logging.getLogger(__name__)


async def record_referral_conversion(
    db,
    referral_id: _uuid.UUID,
    subscription_amount: Decimal,
) -> None:
    """Mark an AccountingPartnerReferral as converted and persist commission data.

    Loads the referral and its parent partner, calculates the first-month
    commission, then writes status, timestamps, and amounts.
    """
    from sqlalchemy import select as _select
    from app.models.accounting_partners import AccountingPartnerReferral
    from app.services.audit import log_action

    try:
        result = await db.execute(
            _select(AccountingPartnerReferral).where(AccountingPartnerReferral.id == referral_id)
        )
        referral = result.scalar_one_or_none()
        if referral is None:
            raise Exception(f"AccountingPartnerReferral {referral_id} not found")

        commission_amount = calculate_commission(
            subscription_amount,
            referral.partner.commission_rate_pct,
            month_number=1,
        )

        referral.status = AccountingPartnerReferral.STATUS_CONVERTED
        referral.converted_at = _datetime.now(_timezone.utc)
        referral.subscription_amount = subscription_amount
        referral.commission_amount = commission_amount

        await db.flush()
        await log_action(
            db=db,
            action="referral.converted",
            resource_type="accounting_partner_referral",
            resource_id=str(referral_id),
            metadata={
                "partner_id": str(referral.partner_id),
                "subscription_amount": str(subscription_amount),
                "commission_amount": str(commission_amount),
            },
        )
        await db.commit()
        _log.info(
            "record_referral_conversion: referral=%s commission=%s",
            referral_id,
            commission_amount,
        )
    except Exception as exc:
        _log.error("record_referral_conversion failed: referral_id=%s error=%s", referral_id, exc)
        await db.rollback()
        raise Exception(f"record_referral_conversion failed: {exc}") from exc


async def record_operator_referral_conversion(
    db,
    referral_id: _uuid.UUID,
    subscription_amount: Decimal,
) -> None:
    """Mark an OperatorReferral as converted and persist commission data."""
    from sqlalchemy import select as _select
    from app.models.operator_referrals import OperatorReferral
    from app.services.audit import log_action

    try:
        result = await db.execute(
            _select(OperatorReferral).where(OperatorReferral.id == referral_id)
        )
        referral = result.scalar_one_or_none()
        if referral is None:
            raise Exception(f"OperatorReferral {referral_id} not found")

        commission_amount = calculate_commission(
            subscription_amount,
            referral.commission_rate_pct,
            month_number=1,
        )

        referral.status = OperatorReferral.STATUS_CONVERTED
        referral.converted_at = _datetime.now(_timezone.utc)
        referral.subscription_amount = subscription_amount
        referral.commission_amount = commission_amount

        await db.flush()
        await log_action(
            db=db,
            action="operator_referral.converted",
            resource_type="operator_referral",
            resource_id=str(referral_id),
            metadata={
                "referrer_org_id": str(referral.referrer_org_id),
                "subscription_amount": str(subscription_amount),
                "commission_amount": str(commission_amount),
            },
        )
        await db.commit()
        _log.info(
            "record_operator_referral_conversion: referral=%s commission=%s",
            referral_id,
            commission_amount,
        )
    except Exception as exc:
        _log.error(
            "record_operator_referral_conversion failed: referral_id=%s error=%s",
            referral_id,
            exc,
        )
        await db.rollback()
        raise Exception(f"record_operator_referral_conversion failed: {exc}") from exc


async def process_monthly_accounting_commissions(db) -> int:
    """Tick down months_remaining for all active accounting-partner referrals.

    Selects every AccountingPartnerReferral with status='converted' and
    months_remaining > 0. For each row, decrements months_remaining by 1;
    when it reaches 0 the referral is marked 'paid_out'.

    Returns the number of referrals processed.
    """
    from sqlalchemy import select as _select
    from app.models.accounting_partners import AccountingPartnerReferral

    try:
        result = await db.execute(
            _select(AccountingPartnerReferral).where(
                AccountingPartnerReferral.status == AccountingPartnerReferral.STATUS_CONVERTED,
                AccountingPartnerReferral.months_remaining > 0,
            )
        )
        referrals = result.scalars().all()
        count = 0
        for referral in referrals:
            referral.months_remaining -= 1
            if referral.months_remaining == 0:
                referral.status = AccountingPartnerReferral.STATUS_PAID_OUT
                referral.paid_out_at = _datetime.now(_timezone.utc)
            count += 1

        await db.commit()
        _log.info("process_monthly_accounting_commissions: processed=%d", count)
        return count
    except Exception as exc:
        _log.error("process_monthly_accounting_commissions failed: %s", exc)
        await db.rollback()
        raise Exception(f"process_monthly_accounting_commissions failed: {exc}") from exc


async def process_monthly_operator_commissions(db) -> int:
    """Tick down months_remaining for all active operator referrals.

    Selects every OperatorReferral with status='converted' and
    months_remaining > 0. For each row, decrements months_remaining by 1;
    when it reaches 0 the referral is marked 'paid_out'.

    Returns the number of referrals processed.
    """
    from sqlalchemy import select as _select
    from app.models.operator_referrals import OperatorReferral

    try:
        result = await db.execute(
            _select(OperatorReferral).where(
                OperatorReferral.status == OperatorReferral.STATUS_CONVERTED,
                OperatorReferral.months_remaining > 0,
            )
        )
        referrals = result.scalars().all()
        count = 0
        for referral in referrals:
            referral.months_remaining -= 1
            if referral.months_remaining == 0:
                referral.status = OperatorReferral.STATUS_PAID_OUT
                referral.paid_out_at = _datetime.now(_timezone.utc)
            count += 1

        await db.commit()
        _log.info("process_monthly_operator_commissions: processed=%d", count)
        return count
    except Exception as exc:
        _log.error("process_monthly_operator_commissions failed: %s", exc)
        await db.rollback()
        raise Exception(f"process_monthly_operator_commissions failed: {exc}") from exc
