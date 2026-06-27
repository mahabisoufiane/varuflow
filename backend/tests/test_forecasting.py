"""Tests for inventory forecasting (Item 41).

Pure + contract-style split (same as Items 28-40). Exercises the pure
engine directly and locks router + plan-gate + analytics integration
via source-text reading.

Required test names (spec):

* test_forecast_30_day
* test_days_until_stockout
* test_moving_average_calculation
* test_at_risk_products_flagged
* test_forecast_vs_actual
* test_export_csv
* test_plan_gate
* test_empty_movement_history_handled
* test_seasonal_pattern_detected
* test_org_isolation
"""
from __future__ import annotations

import pathlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.services import forecasting_engine as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1] / "app"


def _read(relpath: str) -> str:
    return (_BACKEND_ROOT / relpath).read_text()


ROUTER_SRC = _read("routers/forecasting.py")
SERVICE_SRC = _read("services/forecasting_engine.py")
ANALYTICS_SRC = _read("routers/analytics.py")
MAIN_SRC = _read("main.py")


NOW = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)


def _pf(
    *,
    pid=None,
    on_hand=100,
    avg=2.0,
    dus=None,
    at_risk=False,
    trend=svc.TrendDirection.STABLE,
) -> svc.ProductForecast:
    return svc.ProductForecast(
        product_id=pid or uuid.uuid4(),
        name="Widget",
        sku="W-1",
        on_hand=on_hand,
        reorder_level=10,
        avg_daily_demand=avg,
        days_until_stockout=dus,
        forecast_30=max(0, on_hand - int(round(avg * 30))),
        forecast_60=max(0, on_hand - int(round(avg * 60))),
        forecast_90=max(0, on_hand - int(round(avg * 90))),
        trend=trend,
        at_risk=at_risk,
    )


# ═══════════════════════════════════════════════════════════════════
# 1. test_forecast_30_day
# ═══════════════════════════════════════════════════════════════════


def test_forecast_30_day():
    # 100 on hand, burning 2 / day → 40 units at 30 days.
    assert svc.forecast_stock_level(100, 2.0, 30) == 40
    # 60-day horizon drops to -20 → clamped at 0.
    assert svc.forecast_stock_level(100, 2.0, 60) == 0
    # 90-day — also floor-clamped.
    assert svc.forecast_stock_level(100, 2.0, 90) == 0
    # Horizon 0 returns on_hand unchanged.
    assert svc.forecast_stock_level(100, 2.0, 0) == 100
    # Zero demand: stock is unchanged no matter the horizon.
    assert svc.forecast_stock_level(100, 0.0, 90) == 100

    # The engine always reports the 30/60/90 horizons.
    assert svc.DEFAULT_HORIZONS == (30, 60, 90)
    # Router advertises those horizons in its response payload.
    assert "horizon_days=list(svc.DEFAULT_HORIZONS)" in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 2. test_days_until_stockout
# ═══════════════════════════════════════════════════════════════════


def test_days_until_stockout():
    # 100 on hand, 5 / day → 20 days.
    assert svc.days_until_stockout(100, 5.0) == 20.0
    # Non-integer demand — value is a float.
    assert svc.days_until_stockout(100, 2.5) == 40.0
    # Zero demand → None (never runs out at this rate).
    assert svc.days_until_stockout(100, 0.0) is None
    assert svc.days_until_stockout(100, -1.0) is None
    # Zero stock with positive demand = "already out".
    assert svc.days_until_stockout(0, 5.0) == 0.0
    # Negative on-hand (should never happen but must not crash).
    assert svc.days_until_stockout(-5, 5.0) == 0.0


# ═══════════════════════════════════════════════════════════════════
# 3. test_moving_average_calculation
# ═══════════════════════════════════════════════════════════════════


def test_moving_average_calculation():
    # 7-day window over 10 days — matches left edge behaviour.
    series = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    ma = svc.moving_average(series, 7)
    assert len(ma) == 10
    # First 6 values are partial windows.
    assert ma[0] == 1.0
    assert ma[1] == pytest.approx(1.5, rel=1e-6)
    assert ma[2] == pytest.approx(2.0, rel=1e-6)
    # Window 7 is saturated from index 6 onward.
    assert ma[6] == pytest.approx((1 + 2 + 3 + 4 + 5 + 6 + 7) / 7, rel=1e-6)
    assert ma[9] == pytest.approx((4 + 5 + 6 + 7 + 8 + 9 + 10) / 7, rel=1e-6)
    # Empty / zero-window returns empty.
    assert svc.moving_average([], 7) == []
    assert svc.moving_average([1, 2, 3], 0) == []

    # Average-daily-demand is the whole-series mean.
    assert svc.average_daily_demand([3, 3, 3]) == 3.0
    assert svc.average_daily_demand([]) == 0.0


# ═══════════════════════════════════════════════════════════════════
# 4. test_at_risk_products_flagged
# ═══════════════════════════════════════════════════════════════════


def test_at_risk_products_flagged():
    # 3 products: one at risk (5 days), one safe (100 days),
    # one with no demand (None).
    at = _pf(dus=5.0, at_risk=True)
    safe = _pf(dus=100.0, at_risk=False)
    idle = _pf(dus=None, at_risk=False)
    flagged = svc.at_risk_products([at, safe, idle], horizon_days=30)
    assert [f.product_id for f in flagged] == [at.product_id]

    # With a 120-day horizon, the "safe" product joins.
    flagged2 = svc.at_risk_products([at, safe, idle], horizon_days=120)
    assert {f.product_id for f in flagged2} == {at.product_id, safe.product_id}

    # Idle products (days_until = None) are never at risk regardless
    # of horizon — they have no consumption to worry about.
    flagged3 = svc.at_risk_products([idle], horizon_days=10_000)
    assert flagged3 == []

    # Router exposes the at-risk list endpoint.
    assert '@router.get("/at-risk"' in ROUTER_SRC
    assert "at_risk_products" in SERVICE_SRC


# ═══════════════════════════════════════════════════════════════════
# 5. test_forecast_vs_actual
# ═══════════════════════════════════════════════════════════════════


def test_forecast_vs_actual():
    pid = uuid.uuid4()
    rows = svc.compare_forecast_vs_actual([(pid, 100, 120)])
    assert len(rows) == 1
    row = rows[0]
    assert row.forecast == 100
    assert row.actual == 120
    assert row.variance == 20
    assert row.variance_pct == pytest.approx(0.2, abs=1e-4)

    # Zero-forecast doesn't blow up the rate.
    zero = svc.compare_forecast_vs_actual([(pid, 0, 5)])[0]
    assert zero.variance == 5
    assert zero.variance_pct == 0.0

    # Router wires the comparator to /{id}/compare.
    assert "def compare_product" in ROUTER_SRC
    assert "compare_forecast_vs_actual" in SERVICE_SRC


# ═══════════════════════════════════════════════════════════════════
# 6. test_export_csv
# ═══════════════════════════════════════════════════════════════════


def test_export_csv():
    rows = [
        _pf(on_hand=50, avg=2.0, dus=25.0, at_risk=True),
        _pf(on_hand=200, avg=0.5, dus=None, at_risk=False),
    ]
    body = svc.build_forecast_csv(rows)
    import csv, io
    parsed = list(csv.reader(io.StringIO(body)))
    # Header is stable — the columns are grepped by downstream data
    # importers.
    assert parsed[0] == [
        "product_id", "sku", "name", "on_hand", "reorder_level",
        "avg_daily_demand", "days_until_stockout",
        "forecast_30", "forecast_60", "forecast_90",
        "trend", "at_risk",
    ]
    assert len(parsed) == 3  # header + 2 rows
    # None days-until renders as empty, not "None".
    assert parsed[2][6] == ""
    # at_risk column is yes/no.
    assert parsed[1][-1] == "yes"
    assert parsed[2][-1] == "no"

    # Empty input still returns the header — safe default so an empty
    # tenant download still names the schema.
    header_only = svc.build_forecast_csv([])
    assert header_only.strip().startswith("product_id")

    # Router export endpoint audits + sets Content-Disposition.
    assert 'action="forecast.exported"' in ROUTER_SRC
    assert 'filename="forecast.csv"' in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 7. test_plan_gate
# ═══════════════════════════════════════════════════════════════════


def test_plan_gate():
    # Every endpoint in forecasting.py must depend on require_plan(PRO).
    assert ROUTER_SRC.count("Depends(require_plan(OrgPlan.PRO))") >= 5
    assert "from app.middleware.plan_check import require_plan" in ROUTER_SRC
    # Dependency import from OrgPlan.
    assert "from app.models.organization import OrgPlan" in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 8. test_empty_movement_history_handled
# ═══════════════════════════════════════════════════════════════════


def test_empty_movement_history_handled():
    # No movements → series of zeros → avg 0 → dus None → not at risk.
    empty_series = svc.daily_outflow_series([], lookback_days=30, now=NOW)
    assert len(empty_series) == 30
    assert all(v == 0 for v in empty_series)
    assert svc.average_daily_demand(empty_series) == 0.0
    assert svc.days_until_stockout(100, svc.average_daily_demand(empty_series)) is None

    # Trend detection on empty is STABLE, not a crash.
    assert svc.detect_seasonality([]) == svc.TrendDirection.STABLE
    assert svc.detect_seasonality([0] * 30) == svc.TrendDirection.STABLE

    # Lookback 0 returns an empty series (guard against a zero query).
    assert svc.daily_outflow_series([], lookback_days=0, now=NOW) == []


# ═══════════════════════════════════════════════════════════════════
# 9. test_seasonal_pattern_detected
# ═══════════════════════════════════════════════════════════════════


def test_seasonal_pattern_detected():
    # 30 days where the last 7 days are 3× the prior 23.
    low = [1] * 23
    spike = [5] * 7
    assert svc.detect_seasonality(low + spike) == svc.TrendDirection.UP

    # Reverse — last 7 days are a collapse.
    high = [5] * 23
    crash = [1] * 7
    assert svc.detect_seasonality(high + crash) == svc.TrendDirection.DOWN

    # Flat series within the band → STABLE.
    flat = [3] * 30
    assert svc.detect_seasonality(flat) == svc.TrendDirection.STABLE

    # Small wiggle inside the band — still STABLE.
    wiggly = [3, 3, 3, 4, 3, 3, 3] * 4 + [3, 3]  # 30 entries
    assert svc.detect_seasonality(wiggly) == svc.TrendDirection.STABLE

    # Bucketing with real timestamps — outflows on the last day land
    # in the tail bucket, not the head.
    series = svc.daily_outflow_series(
        [
            (NOW, -5),                          # today's outflow
            (NOW - timedelta(days=29), -3),    # oldest
            (NOW - timedelta(days=15), -2),    # middle
            (NOW - timedelta(days=15), +50),   # IN — must be ignored
        ],
        lookback_days=30,
        now=NOW,
    )
    assert len(series) == 30
    assert series[-1] == 5          # today
    assert series[0] == 3           # 29 days ago (oldest bucket)
    assert series[14] == 2          # 15 days ago
    # IN movements are not counted as outflow.
    assert sum(series) == 5 + 3 + 2


# ═══════════════════════════════════════════════════════════════════
# 10. test_org_isolation
# ═══════════════════════════════════════════════════════════════════


def test_org_isolation():
    # Every DB-bound helper filters by org_id.
    assert "Product.org_id == org_id" in SERVICE_SRC
    assert "StockLevel.org_id == org_id" in SERVICE_SRC
    assert "StockMovement.org_id == org_id" in SERVICE_SRC
    # Router always resolves org_id before touching the engine.
    assert "org_id = _org(ctx)" in ROUTER_SRC
    assert ROUTER_SRC.count("org_id=org_id") >= 3

    # Router surfaces 404 for unknown product ids.
    assert 'detail="product_not_found"' in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# Additional invariants
# ═══════════════════════════════════════════════════════════════════


def test_analytics_overview_includes_forecast_count():
    # The analytics overview now carries a stockout_risk_count, wired
    # via the forecasting engine so the two numbers never drift.
    assert "stockout_risk_count" in ANALYTICS_SRC
    assert "_stockout_risk_count" in ANALYTICS_SRC
    assert "forecasting_engine" in ANALYTICS_SRC


def test_router_registered_in_main():
    assert "forecasting.router" in MAIN_SRC
    assert "forecasting," in MAIN_SRC


def test_gather_sort_order_is_at_risk_first():
    # Helper sorts at-risk products to the top of the list so the UI
    # surfaces them without a second pass. The sort key is inlined;
    # assert it via source-text.
    assert "0 if f.at_risk else 1" in SERVICE_SRC


def test_forecast_to_dict_roundtrip():
    pf = _pf(on_hand=40, avg=2.0, dus=20.0, at_risk=True, trend=svc.TrendDirection.UP)
    d = pf.to_dict()
    assert d["on_hand"] == 40
    assert d["forecast_30"] == 0  # 40 - 2*30 = -20 → clamped to 0 via _pf logic
    assert d["trend"] == "up"
    assert d["at_risk"] is True
    # None days-until-stockout serialises as None, not the string "None".
    idle = _pf(avg=0.0, dus=None)
    assert idle.to_dict()["days_until_stockout"] is None
