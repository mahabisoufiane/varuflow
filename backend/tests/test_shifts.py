"""Item 67 — Shifts & payroll."""
from __future__ import annotations

import pathlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.services import shift as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(p: str) -> str:
    return (_BACKEND_ROOT / p).read_text()


MIGRATION_SRC = _read("migrations/versions/e6f8a0b2c5d6_v75_shifts.py")
MODEL_SRC = _read("app/models/shift.py")
SERVICE_SRC = _read("app/services/shift.py")
ROUTER_SRC = _read("app/routers/shifts.py")
MAIN_SRC = _read("app/main.py")


def _ts(y=2026, m=4, d=24, hh=9, mm=0) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=timezone.utc)


# ── Pure service: shift bounds ────────────────────────────────────────────


def test_validate_shift_rejects_naive_datetime():
    with pytest.raises(ValueError):
        svc.validate_shift_bounds(datetime(2026, 4, 24, 9), _ts(hh=10))


def test_validate_shift_requires_end_after_start():
    with pytest.raises(ValueError):
        svc.validate_shift_bounds(_ts(hh=10), _ts(hh=9))
    with pytest.raises(ValueError):
        svc.validate_shift_bounds(_ts(hh=10), _ts(hh=10))


def test_validate_shift_enforces_min_and_max_duration():
    svc.validate_shift_bounds(_ts(hh=9), _ts(hh=9, mm=15))
    svc.validate_shift_bounds(_ts(hh=0), _ts(hh=16))
    with pytest.raises(ValueError):
        svc.validate_shift_bounds(_ts(hh=9), _ts(hh=9, mm=14))
    with pytest.raises(ValueError):
        svc.validate_shift_bounds(_ts(hh=0), _ts(hh=16, mm=1))


def test_validate_notes_and_hourly_rate():
    assert svc.validate_notes(None) is None
    svc.validate_notes("x" * svc.MAX_NOTE_LENGTH)
    with pytest.raises(ValueError):
        svc.validate_notes("x" * (svc.MAX_NOTE_LENGTH + 1))

    assert svc.validate_hourly_rate(None) is None
    assert svc.validate_hourly_rate("125.50") == Decimal("125.50")
    for bad in (Decimal("0"), Decimal("-1"), True, Decimal("100001")):
        with pytest.raises(ValueError):
            svc.validate_hourly_rate(bad)  # type: ignore[arg-type]


# ── Pure service: overlap ─────────────────────────────────────────────────


def _span(sid, staff, s, e):
    return svc.ShiftSpan(id=sid, staff_id=staff, start=s, end=e)


def test_overlap_finds_clashing_shift():
    existing = [_span("a", "s1", _ts(hh=9), _ts(hh=12))]
    cand = _span("b", "s1", _ts(hh=11), _ts(hh=13))
    clash = svc.detect_overlap(cand, existing)
    assert clash is not None and clash.id == "a"


def test_overlap_ignores_touching_boundary():
    existing = [_span("a", "s1", _ts(hh=9), _ts(hh=12))]
    cand = _span("b", "s1", _ts(hh=12), _ts(hh=14))
    assert svc.detect_overlap(cand, existing) is None


def test_overlap_scopes_to_same_staff_and_excludes_self():
    existing = [
        _span("a", "s1", _ts(hh=9), _ts(hh=12)),
        _span("b", "s2", _ts(hh=9), _ts(hh=12)),
    ]
    cand = _span("c", "s2", _ts(hh=11), _ts(hh=13))
    clash = svc.detect_overlap(cand, existing)
    assert clash is not None and clash.id == "b"
    # Self-exclusion: an edit of "a" shouldn't clash with itself.
    self_edit = _span("a", "s1", _ts(hh=10), _ts(hh=11))
    assert svc.detect_overlap(self_edit, existing) is None


# ── Pure service: quarter rounding and hours ──────────────────────────────


def test_round_to_quarter_nearest():
    assert svc.round_to_quarter(_ts(hh=9, mm=7)) == _ts(hh=9, mm=0)
    assert svc.round_to_quarter(_ts(hh=9, mm=8)) == _ts(hh=9, mm=15)
    assert svc.round_to_quarter(_ts(hh=9, mm=53)) == _ts(hh=10, mm=0)


def test_hours_between_precision():
    assert svc.hours_between(_ts(hh=9), _ts(hh=10, mm=30)) == Decimal("1.5000")
    assert svc.hours_between(_ts(hh=9), _ts(hh=9)) == Decimal("0")


def test_open_punch_and_close_punch_rules():
    svc.open_punch(existing_open=0, shift_has_ended=False)
    with pytest.raises(ValueError):
        svc.open_punch(existing_open=1, shift_has_ended=False)
    with pytest.raises(ValueError):
        svc.open_punch(existing_open=0, shift_has_ended=True)

    assert svc.close_punch(_ts(hh=9), _ts(hh=10)) == Decimal("1.0000")
    with pytest.raises(ValueError):
        svc.close_punch(_ts(hh=10), _ts(hh=9))


# ── Pure service: payroll aggregation ─────────────────────────────────────


def test_aggregate_payroll_clips_to_period_and_sums_by_staff():
    punches = [
        ("s1", _ts(d=23, hh=22), _ts(d=24, hh=2),  Decimal("100")),  # 2 in-period
        ("s1", _ts(d=24, hh=9),  _ts(d=24, hh=13), Decimal("100")),  # 4
        ("s2", _ts(d=24, hh=10), _ts(d=24, hh=12), None),              # 2
        ("s3", _ts(d=24, hh=9),  None,              Decimal("50")),   # unclosed
    ]
    rows = svc.aggregate_payroll(
        punches,
        period_start=_ts(d=24, hh=0),
        period_end=_ts(d=25, hh=0),
    )
    by_id = {r.staff_id: r for r in rows}
    assert by_id["s1"].hours == Decimal("6.0000")
    assert by_id["s1"].gross_amount == Decimal("600.00")
    assert by_id["s2"].hours == Decimal("2.0000")
    assert by_id["s2"].gross_amount is None
    assert "s3" not in by_id


def test_aggregate_payroll_rejects_inverted_period():
    with pytest.raises(ValueError):
        svc.aggregate_payroll([], period_start=_ts(hh=10), period_end=_ts(hh=9))


def test_render_payroll_csv_header_and_rows():
    rows = [
        svc.PayrollRow(
            staff_id="s1",
            hours=Decimal("4.0000"),
            hourly_rate=Decimal("125.50"),
            gross_amount=Decimal("502.00"),
        ),
        svc.PayrollRow(
            staff_id="s2",
            hours=Decimal("2.5000"),
            hourly_rate=None,
            gross_amount=None,
        ),
    ]
    csv_text = svc.render_payroll_csv(rows)
    lines = csv_text.strip().splitlines()
    assert lines[0] == "staff_id,hours,hourly_rate,gross_amount"
    assert lines[1] == "s1,4.0000,125.50,502.00"
    assert lines[2] == "s2,2.5000,,"


# ── Migration + model ─────────────────────────────────────────────────────


def test_migration_v75_chains_from_v74():
    assert 'revision = "e6f8a0b2c5d6"' in MIGRATION_SRC
    assert 'down_revision = "d5e7f9a1b4c5"' in MIGRATION_SRC


def test_migration_creates_two_tables():
    assert 'create_table(\n        "shifts"' in MIGRATION_SRC
    assert 'create_table(\n        "shift_punches"' in MIGRATION_SRC
    assert "uq_shifts_staff_start" in MIGRATION_SRC


def test_model_has_shift_and_punch():
    assert "class Shift(Base)" in MODEL_SRC
    assert "class ShiftPunch(Base)" in MODEL_SRC
    assert "uq_shifts_staff_start" in MODEL_SRC


# ── Router source-contract ────────────────────────────────────────────────


def test_router_registered_on_api_shifts():
    assert 'prefix="/api/shifts"' in ROUTER_SRC
    assert "app.include_router(shifts.router)" in MAIN_SRC


def test_router_has_seven_endpoints():
    for sig in (
        '@router.get("", response_model=list[ShiftOut])',
        '@router.post("", response_model=ShiftOut',
        '@router.patch("/{shift_id}"',
        '@router.delete("/{shift_id}"',
        '@router.post("/{shift_id}/clock-in"',
        '@router.post("/{shift_id}/clock-out"',
        '@router.get("/payroll.csv")',
    ):
        assert sig in ROUTER_SRC, f"missing signature: {sig}"


def test_router_scopes_staff_to_caller_org():
    assert "Staff.org_id == org_id" in ROUTER_SRC


def test_router_returns_409_on_overlap():
    assert '"shift overlaps existing"' in ROUTER_SRC


def test_router_payroll_requires_ordered_range():
    assert '"end must be after start"' in ROUTER_SRC


def test_router_logs_all_mutations():
    for action in (
        '"shift.created"',
        '"shift.updated"',
        '"shift.deleted"',
        '"shift.clock_in"',
        '"shift.clock_out"',
    ):
        assert action in ROUTER_SRC, f"missing audit action: {action}"
