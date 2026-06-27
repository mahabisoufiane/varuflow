"""Inventory forecasting engine (Item 41).

Pure + DB-bound split (same pattern as Items 30-40).

Pure layer (no ORM imports — exercised directly in the 3.9 sandbox):

* :func:`daily_outflow_series` — bucket ``StockMovement`` rows into a
  per-day outflow series.
* :func:`moving_average` — simple moving average over a window.
* :func:`average_daily_demand` — mean daily demand over a lookback
  window; collapses to zero for products with zero history so the
  stockout-forecaster returns "never" rather than NaN.
* :func:`days_until_stockout` — on-hand / avg-daily-demand; returns
  ``None`` when demand is zero (never runs out).
* :func:`forecast_stock_level` — projected stock at horizon days;
  clamps at zero so the UI doesn't draw a negative column.
* :func:`detect_seasonality` — ratio of the last-window moving-average
  to the full-period average. > 1.15 = trending up, < 0.85 = trending
  down, inside the band = stable. Pure index detection (no external
  libs); good enough for SMB weekly seasonality.
* :func:`at_risk_products` — flags products whose days-until-stockout
  falls inside a configurable horizon (default 30d).
* :func:`build_forecast_csv` — stdlib CSV with quoted fields.

DB layer (lazy ORM imports):

* :func:`gather_product_metrics` — one-shot SQL aggregate producing a
  :class:`ProductForecast` per active product.
* :func:`build_forecast_report` — scope to a single org.
"""
from __future__ import annotations

import csv
import enum
import io
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Iterable


# ═══════════════════════════════════════════════════════════════════
# Types + constants (pure)
# ═══════════════════════════════════════════════════════════════════


# Default forecast horizons in days. The spec calls for 30/60/90 so
# the three values below are grepped by the test suite to guarantee
# they are always available.
DEFAULT_HORIZONS: tuple[int, ...] = (30, 60, 90)

# Stockout risk horizon — any product whose projected days-until-
# stockout is ≤ this many days is flagged "at risk" on the dashboard.
DEFAULT_AT_RISK_DAYS = 30

# Lookback used to compute average-daily-demand. 30 days strikes a
# balance between signal (enough data to smooth random noise) and
# freshness (a SKU that recently became a best-seller should reflect
# that within a month rather than being drowned out by last year's
# pattern). Caller can override for longer-horizon forecasts.
DEFAULT_LOOKBACK_DAYS = 30

# Moving-average window used for seasonal-trend detection. 7 days
# captures weekly seasonality which is by far the dominant pattern
# for Swedish SMB retail (payday-week spikes, weekend hospitality).
DEFAULT_MA_WINDOW = 7


class TrendDirection(str, enum.Enum):
    UP = "up"         # recent-window MA > full-period × (1 + band)
    DOWN = "down"     # recent-window MA < full-period × (1 - band)
    STABLE = "stable"


@dataclass
class ProductForecast:
    product_id: uuid.UUID
    name: str
    sku: str
    on_hand: int
    reorder_level: int
    avg_daily_demand: float
    days_until_stockout: float | None
    forecast_30: int
    forecast_60: int
    forecast_90: int
    trend: TrendDirection
    at_risk: bool

    def to_dict(self) -> dict:
        return {
            "product_id": str(self.product_id),
            "name": self.name,
            "sku": self.sku,
            "on_hand": self.on_hand,
            "reorder_level": self.reorder_level,
            "avg_daily_demand": round(self.avg_daily_demand, 4),
            "days_until_stockout": (
                None if self.days_until_stockout is None
                else round(self.days_until_stockout, 2)
            ),
            "forecast_30": self.forecast_30,
            "forecast_60": self.forecast_60,
            "forecast_90": self.forecast_90,
            "trend": self.trend.value,
            "at_risk": self.at_risk,
        }


# ═══════════════════════════════════════════════════════════════════
# Pure math
# ═══════════════════════════════════════════════════════════════════


def daily_outflow_series(
    movements: Iterable[tuple[datetime, int]],
    *,
    lookback_days: int,
    now: datetime,
) -> list[int]:
    """Bucket ``(timestamp, signed_qty)`` movements into a per-day
    outflow list.

    Output has exactly ``lookback_days`` entries indexed [oldest ..
    newest]. Only OUT movements (negative qty) contribute; IN /
    ADJUSTMENT are ignored so the forecast models consumption, not
    replenishment. A day with no outflow is zero — no gaps in the
    series so downstream averages / moving-windows are well-defined.
    """
    if lookback_days <= 0:
        return []
    bucket = [0] * lookback_days
    # Newest bucket is "today" (inclusive). Oldest bucket is
    # lookback_days - 1 days ago.
    cutoff = (now - timedelta(days=lookback_days - 1)).date()
    for ts, qty in movements:
        # Consumption only — IN / ADJUSTMENT flipped positive quantities.
        # StockMovement.quantity is signed on OUT rows (negative) in
        # the same schema used by the scheduler's stockout job.
        if qty >= 0:
            continue
        d = ts.date() if isinstance(ts, datetime) else ts
        if d < cutoff or d > now.date():
            continue
        idx = (d - cutoff).days
        if 0 <= idx < lookback_days:
            bucket[idx] += abs(int(qty))
    return bucket


def moving_average(series: list[int], window: int) -> list[float]:
    """Return a list the same length as ``series`` where each cell is
    the mean over the trailing ``window`` entries (or as many as are
    available near the left edge). Empty or zero-window input returns
    an empty list so callers can short-circuit."""
    if not series or window <= 0:
        return []
    out: list[float] = []
    for i in range(len(series)):
        start = max(0, i - window + 1)
        chunk = series[start : i + 1]
        out.append(sum(chunk) / len(chunk) if chunk else 0.0)
    return out


def average_daily_demand(series: list[int]) -> float:
    if not series:
        return 0.0
    return sum(series) / len(series)


def days_until_stockout(
    on_hand: int, avg_daily: float,
) -> float | None:
    """Return days until on-hand hits zero, or ``None`` when demand is
    zero (never runs out at the current rate) so the UI shows ∞ rather
    than a divide-by-zero."""
    if avg_daily <= 0:
        return None
    if on_hand <= 0:
        return 0.0
    return on_hand / avg_daily


def forecast_stock_level(
    on_hand: int, avg_daily: float, horizon_days: int,
) -> int:
    """Projected stock level at ``horizon_days``.

    Floor-clamped at zero — you can't hold negative inventory, and
    showing a negative column on the UI is worse than showing zero
    (the stockout flag handles the real signal).
    """
    if horizon_days <= 0 or avg_daily <= 0:
        return max(0, int(on_hand))
    projected = on_hand - (avg_daily * horizon_days)
    return max(0, int(round(projected)))


def detect_seasonality(
    series: list[int],
    *,
    window: int = DEFAULT_MA_WINDOW,
    band: float = 0.15,
) -> TrendDirection:
    """Classify the trend using a moving-average ratio.

    Compares the most-recent ``window`` days (mean) to the overall
    series mean. If the recent mean is more than ``(1 + band)`` times
    the overall mean → UP. Below ``(1 - band)`` → DOWN. Otherwise
    STABLE. ``band`` = 0.15 is a conservative 15 % threshold chosen
    so day-of-week noise doesn't flip the flag on a flat series.
    """
    if not series or window <= 0:
        return TrendDirection.STABLE
    overall = average_daily_demand(series)
    if overall <= 0:
        # Zero history = can't detect a trend; keep neutral.
        return TrendDirection.STABLE
    recent_window = series[-window:] if len(series) >= window else series
    recent = average_daily_demand(recent_window)
    ratio = recent / overall
    if ratio >= 1.0 + band:
        return TrendDirection.UP
    if ratio <= 1.0 - band:
        return TrendDirection.DOWN
    return TrendDirection.STABLE


def at_risk_products(
    forecasts: Iterable[ProductForecast],
    *,
    horizon_days: int = DEFAULT_AT_RISK_DAYS,
) -> list[ProductForecast]:
    """Return the forecasts whose days-until-stockout falls inside
    ``horizon_days``. Products with zero demand (days_until = None)
    are NOT at risk — they have no outbound consumption to worry
    about, so a low stock level there is intentional."""
    out: list[ProductForecast] = []
    for f in forecasts:
        if f.days_until_stockout is None:
            continue
        if f.days_until_stockout <= horizon_days:
            out.append(f)
    return out


# ═══════════════════════════════════════════════════════════════════
# CSV export (pure)
# ═══════════════════════════════════════════════════════════════════


def build_forecast_csv(forecasts: Iterable[ProductForecast]) -> str:
    """Render a forecast list as CSV with stdlib quoting."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "product_id",
        "sku",
        "name",
        "on_hand",
        "reorder_level",
        "avg_daily_demand",
        "days_until_stockout",
        "forecast_30",
        "forecast_60",
        "forecast_90",
        "trend",
        "at_risk",
    ])
    for f in forecasts:
        writer.writerow([
            str(f.product_id),
            f.sku,
            f.name,
            f.on_hand,
            f.reorder_level,
            round(f.avg_daily_demand, 4),
            (
                "" if f.days_until_stockout is None
                else round(f.days_until_stockout, 2)
            ),
            f.forecast_30,
            f.forecast_60,
            f.forecast_90,
            f.trend.value,
            "yes" if f.at_risk else "no",
        ])
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════
# Forecast vs actual (pure)
# ═══════════════════════════════════════════════════════════════════


@dataclass
class ForecastVsActual:
    product_id: uuid.UUID
    forecast: int
    actual: int

    @property
    def variance(self) -> int:
        return self.actual - self.forecast

    @property
    def variance_pct(self) -> float:
        if self.forecast <= 0:
            return 0.0
        return round((self.actual - self.forecast) / self.forecast, 4)

    def to_dict(self) -> dict:
        return {
            "product_id": str(self.product_id),
            "forecast": self.forecast,
            "actual": self.actual,
            "variance": self.variance,
            "variance_pct": self.variance_pct,
        }


def compare_forecast_vs_actual(
    rows: Iterable[tuple[uuid.UUID, int, int]],
) -> list[ForecastVsActual]:
    """Map ``(product_id, forecast, actual)`` tuples into evaluation
    rows. The pure helper is here so the post-period comparator can
    be tested without a database."""
    return [
        ForecastVsActual(product_id=pid, forecast=int(f), actual=int(a))
        for pid, f, a in rows
    ]


# ═══════════════════════════════════════════════════════════════════
# DB-bound layer
# ═══════════════════════════════════════════════════════════════════


async def gather_product_metrics(
    db,
    *,
    org_id: uuid.UUID,
    now: datetime | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    ma_window: int = DEFAULT_MA_WINDOW,
    at_risk_days: int = DEFAULT_AT_RISK_DAYS,
) -> list[ProductForecast]:
    """Build a ``ProductForecast`` per active product in ``org_id``.

    One round-trip for products, one for stock levels, one for
    movements — independent of product count, so an org with 5 000
    SKUs still runs in O(3 queries). The movement query is bounded
    by the lookback window; a tenant with years of history does not
    pay for more than what the forecast actually consumes.
    """
    from sqlalchemy import func, select

    from app.features.inventory.models import (
        Product,
        StockLevel,
        StockMovement,
        StockMovementType,
    )

    moment = now or datetime.now(timezone.utc)
    window_start = moment - timedelta(days=lookback_days)

    products = (
        await db.execute(
            select(Product).where(
                Product.org_id == org_id,
                Product.is_active == True,  # noqa: E712
            )
        )
    ).scalars().all()
    if not products:
        return []

    # Stock on-hand summed across warehouses.
    stock_rows = await db.execute(
        select(
            StockLevel.product_id,
            func.coalesce(func.sum(StockLevel.quantity), 0).label("qty"),
        )
        .where(StockLevel.org_id == org_id)
        .group_by(StockLevel.product_id)
    )
    on_hand_by_pid: dict[uuid.UUID, int] = {
        r.product_id: int(r.qty or 0) for r in stock_rows.all()
    }

    # Movement history within the lookback window. Pull ``(product_id,
    # created_at, quantity)`` in a single query; the pure bucketer
    # does the rest.
    mvmts = await db.execute(
        select(
            StockMovement.product_id,
            StockMovement.created_at,
            StockMovement.quantity,
            StockMovement.type,
        ).where(
            StockMovement.org_id == org_id,
            StockMovement.created_at >= window_start,
        )
    )
    by_product: dict[uuid.UUID, list[tuple[datetime, int]]] = {}
    for row in mvmts.all():
        # StockMovement stores a positive ``quantity`` — infer signed
        # outflow from ``type``. OUT rows are consumption; IN rows
        # are replenishment. ADJUSTMENT / RESERVED are noisy
        # heuristics that don't model demand well, so we leave them
        # out (same carve-out used by auto-reorder forecasting).
        signed = (
            -abs(int(row.quantity))
            if row.type == StockMovementType.OUT
            else abs(int(row.quantity))
        )
        by_product.setdefault(row.product_id, []).append(
            (row.created_at, signed)
        )

    out: list[ProductForecast] = []
    for p in products:
        series = daily_outflow_series(
            by_product.get(p.id, []),
            lookback_days=lookback_days,
            now=moment,
        )
        avg = average_daily_demand(series)
        on_hand = on_hand_by_pid.get(p.id, 0)
        dus = days_until_stockout(on_hand, avg)
        trend = detect_seasonality(series, window=ma_window)
        at_risk = dus is not None and dus <= at_risk_days
        out.append(
            ProductForecast(
                product_id=p.id,
                name=p.name,
                sku=p.sku,
                on_hand=on_hand,
                reorder_level=int(p.reorder_level or 0),
                avg_daily_demand=avg,
                days_until_stockout=dus,
                forecast_30=forecast_stock_level(on_hand, avg, 30),
                forecast_60=forecast_stock_level(on_hand, avg, 60),
                forecast_90=forecast_stock_level(on_hand, avg, 90),
                trend=trend,
                at_risk=at_risk,
            )
        )
    # Sort "at risk first, then by days-until ascending" so the UI's
    # default render surfaces the products the operator must act on.
    out.sort(
        key=lambda f: (
            0 if f.at_risk else 1,
            f.days_until_stockout if f.days_until_stockout is not None else 10**9,
            f.name,
        )
    )
    return out


async def compute_post_period_actuals(
    db,
    *,
    org_id: uuid.UUID,
    product_ids: list[uuid.UUID],
    from_ts: datetime,
    to_ts: datetime,
) -> dict[uuid.UUID, int]:
    """Sum OUT movements per product between ``from_ts`` and ``to_ts``.

    Used by the forecast-vs-actual comparator. Scoped to the supplied
    product ids so a call on a pre-computed forecast doesn't also pull
    data for products that weren't in the original forecast.
    """
    from sqlalchemy import func, select

    from app.features.inventory.models import StockMovement, StockMovementType

    if not product_ids:
        return {}
    rows = await db.execute(
        select(
            StockMovement.product_id,
            func.coalesce(func.sum(StockMovement.quantity), 0).label("qty"),
        ).where(
            StockMovement.org_id == org_id,
            StockMovement.product_id.in_(product_ids),
            StockMovement.type == StockMovementType.OUT,
            StockMovement.created_at >= from_ts,
            StockMovement.created_at < to_ts,
        ).group_by(StockMovement.product_id)
    )
    return {r.product_id: int(r.qty or 0) for r in rows.all()}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
