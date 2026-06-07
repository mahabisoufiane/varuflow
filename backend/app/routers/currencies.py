"""Currency settings & exchange-rate router (v50 — Item 34).

Endpoint map
------------
    GET  /api/currencies                   — list supported ISO codes + symbols
    GET  /api/currencies/base              — current org base currency
    PUT  /api/currencies/base              — change org base currency
    GET  /api/currencies/rates             — latest rates table
    POST /api/currencies/rates/refresh     — manual sweep trigger (admin)
    GET  /api/currencies/convert           — one-off conversion preview
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.currencies import ExchangeRate
from app.models.organization import Organization
from app.services.audit import log_action
from app.services.currency import (
    _ISO4217,
    _SYMBOLS,
    fetch_exchange_rates,
    normalise_code,
    resolve_rate,
    store_rates,
    symbol_for,
)
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/currencies", tags=["currencies"], dependencies=[Depends(require_module("settings"))])


# ── Schemas ───────────────────────────────────────────────────────


class SupportedCurrencyOut(BaseModel):
    code: str
    symbol: str


class BaseCurrencyOut(BaseModel):
    base_currency: str


class BaseCurrencyIn(BaseModel):
    base_currency: str = Field(..., min_length=3, max_length=3)


class RateOut(BaseModel):
    base_currency: str
    target_currency: str
    rate: Decimal
    fetched_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConvertOut(BaseModel):
    from_currency: str
    to_currency: str
    rate: Decimal
    amount: Decimal
    converted: Decimal


# ── Endpoints ─────────────────────────────────────────────────────


@router.get("", response_model=list[SupportedCurrencyOut])
async def list_supported(ctx: tuple = Depends(get_current_member)):
    """Return the set of ISO codes Varuflow recognises, with symbols."""
    return [SupportedCurrencyOut(code=c, symbol=_SYMBOLS.get(c, c)) for c in sorted(_ISO4217)]


@router.get("/base", response_model=BaseCurrencyOut)
async def get_base_currency(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _user, member = ctx
    org = await db.get(Organization, member.org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    return BaseCurrencyOut(base_currency=getattr(org, "base_currency", "SEK") or "SEK")


@router.put("/base", response_model=BaseCurrencyOut)
async def set_base_currency(
    body: BaseCurrencyIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    code = normalise_code(body.base_currency)
    if code is None:
        raise HTTPException(status_code=422, detail="unknown_currency")
    org = await db.get(Organization, member.org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    old = getattr(org, "base_currency", "SEK") or "SEK"
    org.base_currency = code
    await log_action(
        db,
        action="currency.base_changed",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="organization",
        target_id=str(member.org_id),
        request=request,
        extra={"old": old, "new": code},
    )
    await db.commit()
    return BaseCurrencyOut(base_currency=code)


@router.get("/rates", response_model=list[RateOut])
async def list_rates(
    base: str | None = Query(default=None, min_length=3, max_length=3),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Return the most recent ``fetched_at`` row per ``(base, target)`` pair.

    A repeated cron writes duplicate rows — we de-dupe here so the
    table the UI renders stays tight.
    """
    stmt = select(ExchangeRate).order_by(ExchangeRate.fetched_at.desc()).limit(5000)
    if base:
        b = normalise_code(base)
        if b is None:
            raise HTTPException(status_code=422, detail="unknown_base")
        stmt = stmt.where(ExchangeRate.base_currency == b)
    rows = (await db.execute(stmt)).scalars().all()
    seen: set[tuple[str, str]] = set()
    out: list[ExchangeRate] = []
    for row in rows:
        key = (row.base_currency, row.target_currency)
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


@router.post("/rates/refresh", response_model=BaseCurrencyOut)
async def refresh_rates(
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Owner-triggered manual sweep. Same logic as the daily job.

    Returns the base currency used so the UI can confirm the sweep
    was keyed to the right reporting currency.
    """
    user, member = ctx
    org = await db.get(Organization, member.org_id)
    base = getattr(org, "base_currency", "SEK") or "SEK" if org else "SEK"
    rates = await fetch_exchange_rates(base)
    written = await store_rates(db, rates=rates)
    await log_action(
        db,
        action="currency.rates_refreshed",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="exchange_rate",
        target_id=base,
        request=request,
        extra={"written": written, "base": base},
    )
    await db.commit()
    return BaseCurrencyOut(base_currency=base)


@router.get("/convert", response_model=ConvertOut)
async def convert(
    amount: Decimal = Query(..., ge=Decimal("0"), le=Decimal("1000000000")),
    from_currency: str = Query(..., alias="from", min_length=3, max_length=3),
    to_currency: str = Query(..., alias="to", min_length=3, max_length=3),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    f = normalise_code(from_currency)
    t = normalise_code(to_currency)
    if f is None or t is None:
        raise HTTPException(status_code=422, detail="unknown_currency")
    rate = await resolve_rate(db, from_currency=f, to_currency=t)
    from decimal import Decimal as _D

    converted = (amount * rate).quantize(_D("0.01"))
    return ConvertOut(
        from_currency=f,
        to_currency=t,
        rate=rate,
        amount=amount,
        converted=converted,
    )


__all__ = ["router", "symbol_for"]
