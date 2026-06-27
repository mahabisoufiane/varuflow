"""Currency & exchange-rate logic (v50 — Item 34).

Two layers, matching the Items 30–33 isolation pattern:

* **Pure** — code normalisation, arithmetic conversion, symbol /
  locale formatting, rate-table lookup. Testable under Python 3.9
  without Postgres or httpx.
* **DB-bound** — ``get_latest_rate`` (loads the newest row for a
  pair), ``store_rates`` (persists a batch from the fetcher),
  ``fetch_exchange_rates`` (outbound httpx call to
  openexchangerates.org with a graceful fallback).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable


# ── ISO constants ─────────────────────────────────────────────────


_ISO4217 = {
    "SEK", "EUR", "USD", "GBP", "NOK", "DKK", "CHF", "CAD", "AUD", "JPY",
    "CNY", "HKD", "SGD", "AED", "SAR", "QAR", "KWD", "BHD", "OMR", "JOD",
    "ILS", "EGP", "TRY", "PLN", "CZK", "HUF", "RON", "BGN", "HRK",
    "BRL", "MXN", "ARS", "CLP", "COP", "PEN",
    "INR", "PKR", "BDT", "THB", "MYR", "IDR", "PHP", "VND", "KRW", "TWD",
    "ZAR", "NGN", "KES", "GHS", "MAD", "TND",
    "RUB", "UAH", "ISK", "NZD",
}

# Currency symbol per ISO code (subset — everything else renders as code).
_SYMBOLS = {
    "SEK": "kr", "EUR": "€", "USD": "$", "GBP": "£", "NOK": "kr",
    "DKK": "kr", "CHF": "Fr", "CAD": "$", "AUD": "$", "JPY": "¥",
    "CNY": "¥", "HKD": "$", "SGD": "$", "AED": "د.إ", "SAR": "ر.س",
    "ILS": "₪", "EGP": "ج.م", "TRY": "₺", "PLN": "zł", "INR": "₹",
    "BRL": "R$", "MXN": "$", "ZAR": "R", "RUB": "₽", "KRW": "₩",
    "ISK": "kr",
}

# Locale default currency + locale-specific decimal styles. Only the
# locales Varuflow ships UI for (see frontend/messages/*.json).
_LOCALE_DEFAULTS = {
    "en": ("SEK", ",", "."),   # 1,234.56 kr
    "sv": ("SEK", " ", ","),   # 1 234,56 kr
}


# ── Pure helpers ──────────────────────────────────────────────────


def normalise_code(code) -> str | None:
    """Upper-case and validate a currency code.

    Returns ``None`` for inputs that don't resolve to an ISO 4217
    three-letter code we recognise. Fail-closed: an unknown code is
    rejected at the router boundary rather than silently treated as
    the org base currency.
    """
    if code is None:
        return None
    s = str(code).strip().upper()
    if len(s) != 3 or not s.isalpha():
        return None
    return s if s in _ISO4217 else None


def symbol_for(code) -> str:
    """Return a printable symbol for ``code`` (falls back to the code itself)."""
    c = normalise_code(code) or (str(code).upper() if code else "")
    return _SYMBOLS.get(c, c)


def _q(value, places: int = 2) -> Decimal:
    """Quantise half-up to ``places`` decimals. Matches invoicing."""
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    quant = Decimal("1").scaleb(-places)
    return value.quantize(quant, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class ConversionResult:
    """Outcome of a currency conversion."""

    amount: Decimal
    rate: Decimal
    from_currency: str
    to_currency: str


def convert_amount(amount, *, rate, places: int = 2) -> Decimal:
    """Multiply ``amount`` by ``rate`` and quantise. Clamps negatives to 0.

    Uses full Decimal precision for the multiplication; only the
    final result is rounded so long chains don't accumulate bias.
    """
    if amount is None or rate is None:
        return _q(0, places)
    try:
        amt = Decimal(str(amount))
        r = Decimal(str(rate))
    except Exception:
        return _q(0, places)
    if amt <= 0 or r <= 0:
        return _q(0, places) if amt < 0 else _q(amt * r, places)
    return _q(amt * r, places)


def pick_latest_rate(
    rows: Iterable,
    *,
    base: str,
    target: str,
    now: datetime | None = None,
) -> "object | None":
    """From a collection of rate rows, return the newest for a pair.

    Duck-types on ``base_currency`` / ``target_currency`` / ``rate``
    / ``fetched_at`` so tests can pass ``SimpleNamespace`` stand-ins.
    Ignores rows whose ``fetched_at`` is in the future (clock-skew
    defence).
    """
    base_n = normalise_code(base)
    tgt_n = normalise_code(target)
    if base_n is None or tgt_n is None:
        return None
    if base_n == tgt_n:
        return None  # caller handles identity (rate = 1)
    now = now or datetime.now(tz=timezone.utc)
    best = None
    best_at = None
    for row in rows:
        if normalise_code(getattr(row, "base_currency", None)) != base_n:
            continue
        if normalise_code(getattr(row, "target_currency", None)) != tgt_n:
            continue
        fetched = getattr(row, "fetched_at", None)
        if fetched is None:
            continue
        fetched_utc = fetched if fetched.tzinfo else fetched.replace(tzinfo=timezone.utc)
        if fetched_utc > now:
            continue
        if best_at is None or fetched_utc > best_at:
            best = row
            best_at = fetched_utc
    return best


def rate_between(rows: Iterable, *, from_currency: str, to_currency: str) -> Decimal | None:
    """Return the rate to multiply ``from`` by to get ``to``, or None.

    Falls back in this order:
      1) direct ``from → to`` row;
      2) ``to → from`` inverted;
      3) triangulated via any common base (``from → X`` × ``X → to``);
      4) identity (``from == to`` → 1).
    """
    f = normalise_code(from_currency)
    t = normalise_code(to_currency)
    if f is None or t is None:
        return None
    if f == t:
        return Decimal("1")
    rows_list = list(rows)
    direct = pick_latest_rate(rows_list, base=f, target=t)
    if direct is not None:
        return Decimal(str(getattr(direct, "rate")))
    inverse = pick_latest_rate(rows_list, base=t, target=f)
    if inverse is not None:
        r = Decimal(str(getattr(inverse, "rate")))
        if r != 0:
            return _q(Decimal("1") / r, places=8)
    # Triangulate via any ``X`` we have both legs for.
    seen_mids: set[str] = set()
    for row in rows_list:
        for side in ("base_currency", "target_currency"):
            mid = normalise_code(getattr(row, side, None))
            if mid is None or mid == f or mid == t or mid in seen_mids:
                continue
            seen_mids.add(mid)
            leg1 = rate_direct(rows_list, base=f, target=mid)
            leg2 = rate_direct(rows_list, base=mid, target=t)
            if leg1 is not None and leg2 is not None:
                return _q(leg1 * leg2, places=8)
    return None


def rate_direct(rows: Iterable, *, base: str, target: str) -> Decimal | None:
    """Direct-or-inverse rate lookup. Helper for triangulation.

    Returns the rate as a ``Decimal`` (inverting when only the
    reverse row exists) or ``None``. Separated from ``rate_between``
    to avoid recursing into triangulation inside triangulation.
    """
    f = normalise_code(base)
    t = normalise_code(target)
    if f is None or t is None:
        return None
    if f == t:
        return Decimal("1")
    rows_list = list(rows)
    direct = pick_latest_rate(rows_list, base=f, target=t)
    if direct is not None:
        return Decimal(str(getattr(direct, "rate")))
    inverse = pick_latest_rate(rows_list, base=t, target=f)
    if inverse is not None:
        r = Decimal(str(getattr(inverse, "rate")))
        if r != 0:
            return _q(Decimal("1") / r, places=8)
    return None


def format_amount(amount, code, locale: str = "en") -> str:
    """Render an amount with thousands + decimal separators + symbol.

    Defensive: an unknown locale falls back to ``"en"``; an unknown
    code renders as ``"<amount> <CODE>"`` with no symbol.
    """
    defaults = _LOCALE_DEFAULTS.get((locale or "en")[:2], _LOCALE_DEFAULTS["en"])
    _, thousands, decimal_sep = defaults
    amt = _q(amount)
    negative = amt < 0
    if negative:
        amt = -amt
    whole, _, frac = format(amt, "f").partition(".")
    # Thousands grouping.
    grouped = ""
    while len(whole) > 3:
        grouped = thousands + whole[-3:] + grouped
        whole = whole[:-3]
    grouped = whole + grouped
    body = grouped
    if frac:
        body = f"{grouped}{decimal_sep}{frac}"
    sign = "-" if negative else ""
    c = normalise_code(code)
    sym = _SYMBOLS.get(c, "") if c else ""
    if not sym:
        return f"{sign}{body} {c or (str(code).upper() if code else '')}".strip()
    # Post-amount for SEK/NOK/DKK (scandi-style); pre-amount otherwise.
    if c in ("SEK", "NOK", "DKK", "ISK"):
        return f"{sign}{body} {sym}"
    return f"{sign}{sym}{body}"


def normalise_rate_payload(payload, *, base: str) -> list[tuple[str, str, Decimal]]:
    """Convert an openexchangerates-style JSON ``rates`` dict to triples.

    Filters to codes we recognise via ``_ISO4217`` and drops non-
    numeric entries silently. The outer caller is the httpx fetcher.
    """
    base_n = normalise_code(base) or "SEK"
    if not isinstance(payload, dict):
        return []
    out: list[tuple[str, str, Decimal]] = []
    rates_in = payload.get("rates") if "rates" in payload else payload
    if not isinstance(rates_in, dict):
        return []
    for key, val in rates_in.items():
        tgt = normalise_code(key)
        if tgt is None or tgt == base_n:
            continue
        try:
            out.append((base_n, tgt, Decimal(str(val))))
        except Exception:
            continue
    return out


# ── DB-bound helpers ──────────────────────────────────────────────


async def get_latest_rate_row(db, *, base: str, target: str):
    """Return the newest ``ExchangeRate`` row for a pair, or ``None``.

    Identity (``base == target``) returns ``None``; the caller should
    use rate = 1.
    """
    try:
        from sqlalchemy import select

        from app.models.currencies import ExchangeRate
    except Exception:
        return None
    b = normalise_code(base)
    t = normalise_code(target)
    if b is None or t is None or b == t:
        return None
    row = (
        await db.execute(
            select(ExchangeRate)
            .where(ExchangeRate.base_currency == b, ExchangeRate.target_currency == t)
            .order_by(ExchangeRate.fetched_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return row


async def resolve_rate(db, *, from_currency: str, to_currency: str) -> Decimal:
    """Resolve a currency-pair rate from the DB, with safe fallbacks.

    Returns ``1`` when:
      * identity (``from == to``),
      * either code is unrecognised,
      * or the DB has no rows and the triangulation can't help.

    The ``1`` fallback means a brand-new org with no fetched rates
    yet still writes valid transactions — the rate can be back-
    filled by a later analytics re-run.
    """
    f = normalise_code(from_currency)
    t = normalise_code(to_currency)
    if f is None or t is None or f == t:
        return Decimal("1")
    try:
        from sqlalchemy import select

        from app.models.currencies import ExchangeRate
    except Exception:
        return Decimal("1")
    rows = (
        await db.execute(
            select(ExchangeRate).where(
                ExchangeRate.base_currency.in_((f, t))
            )
        )
    ).scalars().all()
    rate = rate_between(rows, from_currency=f, to_currency=t)
    return rate if rate is not None else Decimal("1")


async def store_rates(db, *, rates: Iterable[tuple[str, str, Decimal]]) -> int:
    """Persist a batch of rate triples. Returns count written.

    Never raises — a bad row is dropped silently so the scheduler
    still finishes its sweep even when the upstream API ships a
    weird payload.
    """
    try:
        from app.models.currencies import ExchangeRate
    except Exception:
        return 0
    import uuid as _uuid

    now = datetime.now(tz=timezone.utc)
    count = 0
    for base, target, rate in rates:
        try:
            db.add(
                ExchangeRate(
                    id=_uuid.uuid4(),
                    base_currency=base,
                    target_currency=target,
                    rate=Decimal(str(rate)),
                    fetched_at=now,
                )
            )
            count += 1
        except Exception:
            continue
    if count:
        try:
            await db.flush()
        except Exception:
            return 0
    return count


async def fetch_exchange_rates(base: str = "SEK") -> list[tuple[str, str, Decimal]]:
    """Call openexchangerates.org and return normalised triples.

    Returns an empty list on any failure (no API key, network error,
    malformed response). The scheduler treats an empty return as
    "nothing to store" rather than crashing the daily job.
    """
    try:
        import httpx

        from app.config import settings
    except Exception:
        return []
    api_key = getattr(settings, "OPEN_EXCHANGE_RATES_API_KEY", "") or ""
    if not api_key:
        return []
    base_n = normalise_code(base) or "SEK"
    url = "https://openexchangerates.org/api/latest.json"
    params = {"app_id": api_key, "base": base_n}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(url, params=params)
        if res.status_code != 200:
            return []
        payload = res.json()
    except Exception:
        return []
    return normalise_rate_payload(payload, base=base_n)
