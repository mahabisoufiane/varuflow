"""Item 54 — Invoice Installment Plans."""
from __future__ import annotations

import pathlib
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.services import invoice_installment as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(relpath: str) -> str:
    # Dir-aware: a router/service split into a package (e.g. routers/invoicing/)
    # is read by concatenating its modules, so source-string assertions still
    # work after the feature-package refactor.
    path = _BACKEND_ROOT / relpath
    if path.is_file():
        return path.read_text()
    pkg = path.with_suffix("")
    if pkg.is_dir():
        return "".join(f.read_text() for f in sorted(pkg.rglob("*.py")))
    return path.read_text()


ROUTER_SRC = _read("app/features/invoicing.py")
MODEL_SRC = _read("app/models/invoice_installment.py")
SERVICE_SRC = _read("app/services/invoice_installment.py")

_V64 = _BACKEND_ROOT / "migrations" / "versions" / "f4a6b8c0d2e7_v64_invoice_installments.py"
MIGRATION_SRC = _V64.read_text() if _V64.exists() else ""


# ── Required 10 tests ──────────────────────────────────────────────────────


def test_installment_creation():
    plan = svc.build_plan(
        total_sek=Decimal("1000.00"),
        parts=4,
        start_date=date(2026, 1, 1),
    )
    assert len(plan) == 4
    assert plan[0].sequence == 1 and plan[-1].sequence == 4
    assert svc.plan_sum(plan) == Decimal("1000.00")
    assert '@router.post(' in ROUTER_SRC
    assert '"/invoices/{invoice_id}/installments"' in ROUTER_SRC
    assert "async def create_installment_plan" in ROUTER_SRC


def test_installment_equal_split_with_remainder():
    """100 / 3 → 33.33, 33.33, 33.34 (remainder on last row)."""
    plan = svc.build_plan(
        total_sek=Decimal("100.00"),
        parts=3,
        start_date=date(2026, 1, 1),
    )
    amounts = [p.amount_sek for p in plan]
    assert amounts[0] == Decimal("33.33")
    assert amounts[1] == Decimal("33.33")
    assert amounts[2] == Decimal("33.34")
    assert sum(amounts) == Decimal("100.00")


def test_installment_due_dates_intervalled():
    plan = svc.build_plan(
        total_sek=Decimal("900.00"),
        parts=3,
        start_date=date(2026, 1, 15),
        interval_days=30,
    )
    assert plan[0].due_date == date(2026, 1, 15)
    assert plan[1].due_date == date(2026, 2, 14)
    assert plan[2].due_date == date(2026, 3, 16)


def test_partial_payment_flips_status():
    new_paid, status = svc.apply_payment(
        paid_amount_sek=Decimal("0.00"),
        amount_sek=Decimal("100.00"),
        payment_sek=Decimal("40.00"),
    )
    assert new_paid == Decimal("40.00")
    assert status == svc.STATUS_PARTIAL


def test_full_payment_marks_paid():
    new_paid, status = svc.apply_payment(
        paid_amount_sek=Decimal("40.00"),
        amount_sek=Decimal("100.00"),
        payment_sek=Decimal("60.00"),
    )
    assert new_paid == Decimal("100.00")
    assert status == svc.STATUS_PAID


def test_overpayment_caps_at_amount():
    new_paid, status = svc.apply_payment(
        paid_amount_sek=Decimal("0.00"),
        amount_sek=Decimal("100.00"),
        payment_sek=Decimal("150.00"),
    )
    assert new_paid == Decimal("100.00")
    assert status == svc.STATUS_PAID


def test_reminder_triggers_within_window():
    today = date(2026, 5, 1)
    # Due in 2 days, never reminded → send.
    assert svc.needs_reminder(
        due_date=today + timedelta(days=2),
        status=svc.STATUS_SCHEDULED,
        last_reminded_at=None,
        today=today,
    ) is True
    # Due in 10 days → too early.
    assert svc.needs_reminder(
        due_date=today + timedelta(days=10),
        status=svc.STATUS_SCHEDULED,
        last_reminded_at=None,
        today=today,
    ) is False
    # Already reminded → suppress.
    assert svc.needs_reminder(
        due_date=today + timedelta(days=1),
        status=svc.STATUS_SCHEDULED,
        last_reminded_at=today,
        today=today,
    ) is False


def test_is_overdue_past_due_date():
    today = date(2026, 5, 1)
    assert svc.is_overdue(
        due_date=date(2026, 4, 20),
        status=svc.STATUS_SCHEDULED,
        today=today,
    ) is True
    assert svc.is_overdue(
        due_date=date(2026, 5, 10),
        status=svc.STATUS_SCHEDULED,
        today=today,
    ) is False
    # Paid installments never overdue.
    assert svc.is_overdue(
        due_date=date(2025, 1, 1),
        status=svc.STATUS_PAID,
        today=today,
    ) is False


def test_installment_audit_logged():
    assert 'action="invoice_installment.plan_created"' in ROUTER_SRC
    assert 'action="invoice_installment.payment_recorded"' in ROUTER_SRC
    assert 'action="invoice_installment.plan_cancelled"' in ROUTER_SRC


def test_installment_payment_endpoint():
    assert '"/installments/{installment_id}/payments"' in ROUTER_SRC
    assert "async def record_installment_payment" in ROUTER_SRC


# ── Invariants ─────────────────────────────────────────────────────────────


def test_migration_v64_chains_from_v63():
    assert 'revision = "f4a6b8c0d2e7"' in MIGRATION_SRC
    assert 'down_revision = "e3f5a7b9c1d5"' in MIGRATION_SRC
    assert "invoice_installments" in MIGRATION_SRC


def test_model_registered():
    assert "class InvoiceInstallment" in MODEL_SRC
    assert "uq_invoice_installments_invoice_sequence" in MODEL_SRC


def test_build_plan_rejects_bad_inputs():
    with pytest.raises(ValueError):
        svc.build_plan(total_sek=Decimal("100"), parts=0, start_date=date.today())
    with pytest.raises(ValueError):
        svc.build_plan(total_sek=Decimal("100"), parts=40, start_date=date.today())
    with pytest.raises(ValueError):
        svc.build_plan(total_sek=Decimal("0"), parts=3, start_date=date.today())


def test_apply_payment_rejects_negative():
    with pytest.raises(ValueError):
        svc.apply_payment(
            paid_amount_sek=Decimal("0"),
            amount_sek=Decimal("100"),
            payment_sek=Decimal("-5"),
        )


def test_service_is_pure():
    low = SERVICE_SRC.lower()
    assert "sqlalchemy" not in low
    assert "httpx" not in low
