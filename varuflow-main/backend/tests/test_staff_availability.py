"""Item 57 — Staff availability overrides.

Pure + source-contract tests. Mirrors the repo style (no DB fixtures,
no HTTP — pure helpers are tested directly, router contract is
verified by reading the source).
"""
from __future__ import annotations

import pathlib
from datetime import datetime, timedelta, timezone

import pytest

from app.services import staff_availability as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(p: str) -> str:
    _p = _BACKEND_ROOT / p
    if _p.is_file():
        return _p.read_text()
    # Path was split into a feature package (e.g. routers/invoicing/);
    # concatenate its modules so source-string assertions still hold.
    _pkg = _p.with_suffix("")
    if _pkg.is_dir():
        return "".join(_f.read_text() for _f in sorted(_pkg.rglob("*.py")))
    return _p.read_text()


MIGRATION_SRC = _read(
    "migrations/versions/b6d8f0a2c4e7_v66_staff_availability.py"
)
MODEL_SRC = _read("app/features/hr/staff_availability.py")
SERVICE_SRC = _read("app/services/staff_availability.py")
ROUTER_SRC = _read("app/features/bookings/bookings.py")


UTC = timezone.utc


def _dt(h: int, m: int = 0, day: int = 1) -> datetime:
    return datetime(2026, 5, day, h, m, tzinfo=UTC)


# ── Pure service ──────────────────────────────────────────────────────────


def test_interval_rejects_non_positive_length():
    with pytest.raises(ValueError):
        svc.Interval(_dt(10), _dt(10))
    with pytest.raises(ValueError):
        svc.Interval(_dt(11), _dt(10))


def test_parse_hhmm_and_window_from_day():
    t = svc.parse_hhmm("09:30")
    assert (t.hour, t.minute) == (9, 30)
    w = svc.window_from_day(_dt(0), "09:00", "17:00")
    assert w.start == _dt(9)
    assert w.end == _dt(17)


def test_subtract_interval_no_overlap():
    base = svc.Interval(_dt(9), _dt(17))
    cut = svc.Interval(_dt(18), _dt(19))
    assert svc.subtract_interval(base, cut) == [base]


def test_subtract_interval_fully_consumed():
    base = svc.Interval(_dt(9), _dt(17))
    cut = svc.Interval(_dt(8), _dt(20))
    assert svc.subtract_interval(base, cut) == []


def test_subtract_interval_middle_split():
    base = svc.Interval(_dt(9), _dt(17))
    cut = svc.Interval(_dt(12), _dt(13))
    out = svc.subtract_interval(base, cut)
    assert len(out) == 2
    assert (out[0].start, out[0].end) == (_dt(9), _dt(12))
    assert (out[1].start, out[1].end) == (_dt(13), _dt(17))


def test_subtract_interval_left_and_right_trim():
    base = svc.Interval(_dt(9), _dt(17))
    assert [(i.start, i.end) for i in svc.subtract_interval(base, svc.Interval(_dt(8), _dt(10)))] == [(_dt(10), _dt(17))]
    assert [(i.start, i.end) for i in svc.subtract_interval(base, svc.Interval(_dt(16), _dt(20)))] == [(_dt(9), _dt(16))]


def test_merge_intervals_combines_overlap_and_touching():
    ivs = [
        svc.Interval(_dt(9), _dt(11)),
        svc.Interval(_dt(10), _dt(12)),
        svc.Interval(_dt(12), _dt(13)),
        svc.Interval(_dt(15), _dt(17)),
    ]
    merged = svc.merge_intervals(ivs)
    assert [(i.start, i.end) for i in merged] == [
        (_dt(9), _dt(13)),
        (_dt(15), _dt(17)),
    ]


def test_apply_overrides_time_off_carves_lunch_out_of_baseline():
    baseline = [svc.Interval(_dt(9), _dt(17))]
    overrides = [svc.Override(kind="time_off", start=_dt(12), end=_dt(13))]
    out = svc.apply_overrides(baseline, overrides)
    assert [(i.start, i.end) for i in out] == [
        (_dt(9), _dt(12)),
        (_dt(13), _dt(17)),
    ]


def test_apply_overrides_extra_shift_adds_evening():
    baseline = [svc.Interval(_dt(9), _dt(17))]
    overrides = [svc.Override(kind="extra_shift", start=_dt(18), end=_dt(21))]
    out = svc.apply_overrides(baseline, overrides)
    assert [(i.start, i.end) for i in out] == [
        (_dt(9), _dt(17)),
        (_dt(18), _dt(21)),
    ]


def test_apply_overrides_sick_day_clears_availability():
    baseline = [svc.Interval(_dt(9), _dt(17))]
    overrides = [svc.Override(kind="sick", start=_dt(0), end=_dt(23, 59))]
    out = svc.apply_overrides(baseline, overrides)
    assert out == []


def test_is_available_exact_and_partial():
    avail = [svc.Interval(_dt(9), _dt(17))]
    assert svc.is_available(svc.Interval(_dt(10), _dt(11)), avail)
    assert not svc.is_available(svc.Interval(_dt(16), _dt(18)), avail)


def test_total_duration_sums():
    ivs = [
        svc.Interval(_dt(9), _dt(10)),
        svc.Interval(_dt(11), _dt(13)),
    ]
    assert svc.total_duration(ivs) == timedelta(hours=3)


# ── Migration + model ─────────────────────────────────────────────────────


def test_migration_v66_chains_from_v65():
    assert 'revision = "b6d8f0a2c4e7"' in MIGRATION_SRC
    assert 'down_revision = "a5c7e9b1d3f6"' in MIGRATION_SRC
    assert "staff_availability_overrides" in MIGRATION_SRC
    assert "ck_staff_availability_range" in MIGRATION_SRC


def test_model_enum_values_match_service_kinds():
    for kind in ("time_off", "sick", "extra_shift", "holiday"):
        assert f'"{kind}"' in MODEL_SRC
    # Service kind registry must agree.
    assert {"time_off", "sick", "holiday"} == set(svc.BLOCKING_KINDS)
    assert {"extra_shift"} == set(svc.ADDITIVE_KINDS)


# ── Router source-contract ────────────────────────────────────────────────


def test_router_has_four_availability_endpoints():
    assert '@router.post(\n    "/staff/{staff_id}/availability"' in ROUTER_SRC
    assert '@router.get(\n    "/staff/{staff_id}/availability"' in ROUTER_SRC
    assert '@router.delete(\n    "/staff/{staff_id}/availability/{override_id}"' in ROUTER_SRC
    assert '/staff/{staff_id}/available-windows' in ROUTER_SRC


def test_router_tenant_scopes_every_access():
    # Staff is fetched and `org_id` compared before any write / read
    # happens. The override row itself is also filtered by org_id in
    # list + delete.
    assert ROUTER_SRC.count("staff_row.org_id != member.org_id") >= 3
    assert "_AvOv_57.org_id == member.org_id" in ROUTER_SRC


def test_router_validates_kind_and_range():
    assert "kind must be one of" in ROUTER_SRC
    assert "end_at must be after start_at" in ROUTER_SRC


def test_router_logs_create_and_delete():
    assert '"staff_availability.created"' in ROUTER_SRC
    assert '"staff_availability.deleted"' in ROUTER_SRC


def test_router_available_windows_applies_overrides():
    assert "apply_overrides" in ROUTER_SRC
    assert "window_from_day" in ROUTER_SRC
