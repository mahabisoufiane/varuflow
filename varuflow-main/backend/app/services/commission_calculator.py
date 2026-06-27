"""Pure commission calculator — no ORM dependencies.

All functions operate on simple data shapes (``Decimal`` + duck-typed
rule rows). This keeps the arithmetic unit-testable without Postgres,
matching the Py-3.9-sandbox isolation pattern from Items 30 and 31.

Rule types
----------
* ``flat``   — a fixed amount paid per qualifying transaction. The
               ``base_amount`` is ignored; ``value`` is the payout.
* ``pct``    — percentage of ``base_amount``. ``value`` is treated as
               a percent (5 → 5%, not 500%).
* ``tiered`` — same as ``pct`` but only applies when
               ``base_amount >= min_threshold``. Sub-threshold
               transactions yield zero commission.

Applies-to filter
-----------------
Each rule carries an ``applies_to`` string. The matcher accepts an
optional ``source_type`` parameter and only returns rules whose
``applies_to`` is ``"all"`` or matches the source. The caller is
responsible for passing the correct source_type per transaction; a
malformed rule with an unknown ``applies_to`` is skipped (fail-closed)
rather than matched as a wildcard.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable


# Rounding precision for currency amounts — two decimals, banker's
# rounding disabled (we use half-up to match the invoicing module).
_TWO_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class CommissionResult:
    """Return value from ``compute_commission``.

    ``rule_id`` is the ``id`` attribute of the winning rule row, or
    ``None`` if no rule matched. ``amount`` is always a quantised
    ``Decimal`` rounded to two decimals.
    """

    amount: Decimal
    rule_id: object | None  # UUID | str | None — kept type-agnostic for tests


def _q(value) -> Decimal:
    """Quantise any number-like input to two decimals, half-up.

    We never quantise midway through a calculation; only the final
    result gets rounded. Intermediate Decimals retain full precision
    so a chain of percentage × amount computations doesn't accumulate
    per-step rounding bias.
    """
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def _applies(rule, source_type: str | None) -> bool:
    """Does this rule match the given source type?

    ``applies_to="all"`` is the wildcard. Anything else must match
    ``source_type`` exactly. A rule with a typo in ``applies_to``
    (e.g. ``"bookings"`` instead of ``"booking"``) never matches —
    safer than silently firing on every source.
    """
    applies_to = getattr(rule, "applies_to", "all")
    if applies_to == "all":
        return True
    if source_type is None:
        return False
    return applies_to == source_type


def match_rules(
    rules: Iterable, *, staff_id, source_type: str | None = None, only_active: bool = True
) -> list:
    """Return the rules that apply to ``staff_id`` + ``source_type``.

    Order-preserving. Callers pick one via ``pick_best_rule``, which
    gives a deterministic tiered-beats-flat tie-break.
    """
    out = []
    for rule in rules:
        if getattr(rule, "staff_id", None) != staff_id:
            continue
        if only_active and not getattr(rule, "is_active", True):
            continue
        if not _applies(rule, source_type):
            continue
        out.append(rule)
    return out


def pick_best_rule(rules: Iterable, *, base_amount) -> object | None:
    """Tie-break: tiered (meeting threshold) > pct > flat > anything else.

    When multiple rules of the same type match, the one with the
    larger ``value`` wins — this matches the "better rule wins" mental
    model operators expect when overlapping definitions exist.
    """
    base = Decimal(str(base_amount or 0))

    def _rank(rule) -> tuple:
        rtype = getattr(rule, "rule_type", "")
        if rtype == "tiered":
            threshold = getattr(rule, "min_threshold", None)
            qualifies = threshold is None or base >= Decimal(str(threshold))
            if not qualifies:
                return (0, Decimal(0))
            return (3, Decimal(str(getattr(rule, "value", 0) or 0)))
        if rtype == "pct":
            return (2, Decimal(str(getattr(rule, "value", 0) or 0)))
        if rtype == "flat":
            return (1, Decimal(str(getattr(rule, "value", 0) or 0)))
        return (0, Decimal(0))

    best = None
    best_rank = (0, Decimal(0))
    for rule in rules:
        rank = _rank(rule)
        if rank > best_rank:
            best = rule
            best_rank = rank
    return best


def apply_rule(rule, base_amount) -> Decimal:
    """Return the commission amount for a single rule + base.

    Negative bases clamp to zero — commissions are never negative.
    Missing / invalid ``value`` yields zero, not an exception.
    """
    if rule is None:
        return Decimal("0.00")
    try:
        base = Decimal(str(base_amount or 0))
    except Exception:
        return Decimal("0.00")
    if base < 0:
        base = Decimal(0)
    try:
        value = Decimal(str(getattr(rule, "value", 0) or 0))
    except Exception:
        return Decimal("0.00")

    rtype = getattr(rule, "rule_type", "")
    if rtype == "flat":
        return _q(value)
    if rtype == "pct":
        return _q((base * value) / Decimal(100))
    if rtype == "tiered":
        threshold = getattr(rule, "min_threshold", None)
        if threshold is not None:
            if base < Decimal(str(threshold)):
                return Decimal("0.00")
        return _q((base * value) / Decimal(100))
    # Unknown rule type — fail closed.
    return Decimal("0.00")


def compute_commission(
    rules: Iterable,
    *,
    staff_id,
    base_amount,
    source_type: str | None = None,
) -> CommissionResult:
    """Top-level helper: pick the best matching rule and compute the amount.

    Returns a ``CommissionResult(amount=Decimal("0.00"), rule_id=None)``
    when no rule matches. This is the function the transaction hooks
    (POS, bookings, invoice payment) call — it's the single place where
    rule selection and arithmetic live together.
    """
    candidates = match_rules(rules, staff_id=staff_id, source_type=source_type)
    rule = pick_best_rule(candidates, base_amount=base_amount)
    if rule is None:
        return CommissionResult(amount=Decimal("0.00"), rule_id=None)
    return CommissionResult(
        amount=apply_rule(rule, base_amount),
        rule_id=getattr(rule, "id", None),
    )


def summarise_run(entries: Iterable) -> dict:
    """Aggregate a list of ``CommissionEntry``-like rows.

    Returns ``{"total": Decimal, "per_staff": {staff_id: Decimal}}``.
    Used by the monthly run report endpoint and by the scheduler when
    it updates ``CommissionRun.total_paid`` on lock.
    """
    total = Decimal("0.00")
    per_staff: dict = {}
    for entry in entries:
        amt = Decimal(str(getattr(entry, "commission_amount", 0) or 0))
        total += amt
        sid = getattr(entry, "staff_id", None)
        per_staff[sid] = per_staff.get(sid, Decimal("0.00")) + amt
    return {"total": _q(total), "per_staff": {k: _q(v) for k, v in per_staff.items()}}


# ── DB-bound hook helper ───────────────────────────────────────────
#
# The transaction hooks on POS, bookings, and invoicing all need the
# same shape: load the org's active rules for this staff, pick the
# best match, persist a ``CommissionEntry`` if the amount is > 0.
# Keeping it here (rather than on each router) guarantees the three
# call sites stay in lockstep.


async def record_commission_for_source(
    db,
    *,
    org_id,
    staff_id,
    source_type: str,
    source_id,
    base_amount,
) -> "object | None":
    """Evaluate rules and, if any apply, insert a ``CommissionEntry``.

    Returns the inserted row, or ``None`` if no rule matched (including
    the case where ``staff_id`` is falsy, which is the default-off
    behaviour for tenants who haven't configured commissions). Never
    raises — commission recording is a side-effect that must not
    break the primary transaction.

    The entry is inserted with ``run_id=None``; the monthly scheduler
    (or a manual ``POST /runs``) sweeps unassigned entries into the
    active run. This lets the hook fire before any run exists.
    """
    if staff_id is None:
        return None
    try:
        from app.features.hr.commissions_models import CommissionEntry, CommissionRule

        rules = (
            await db.execute(
                select_rules_for(staff_id, org_id)
            )
        ).scalars().all()
        result = compute_commission(
            rules,
            staff_id=staff_id,
            base_amount=base_amount,
            source_type=source_type,
        )
        if result.amount <= Decimal("0"):
            return None
        import uuid as _uuid

        entry = CommissionEntry(
            id=_uuid.uuid4(),
            org_id=org_id,
            run_id=None,
            staff_id=staff_id,
            source_type=source_type,
            source_id=str(source_id),
            base_amount=Decimal(str(base_amount or 0)),
            commission_amount=result.amount,
            rule_id=result.rule_id,
        )
        db.add(entry)
        await db.flush()
        return entry
    except Exception:
        # Best-effort: a commission-layer failure must never break
        # the primary POS / booking / invoicing transaction. The
        # audit pipeline will still capture the parent mutation.
        return None


def select_rules_for(staff_id, org_id):
    """Return a SQLAlchemy statement selecting active rules for staff+org.

    Factored out so ``record_commission_for_source`` stays importable
    without pulling sqlalchemy at module load time.
    """
    from sqlalchemy import select

    from app.features.hr.commissions_models import CommissionRule

    return select(CommissionRule).where(
        CommissionRule.org_id == org_id,
        CommissionRule.staff_id == staff_id,
        CommissionRule.is_active.is_(True),
    )


def render_run_csv(run, entries: Iterable) -> str:
    """Render a commission run to CSV text.

    Kept in the pure-calculator module (rather than the router) so
    tests can exercise it under Python 3.9 without importing the
    router's typing chain. Duck-types on ``run`` and ``entries``.
    """
    import csv as _csv
    import io as _io

    buf = _io.StringIO()
    writer = _csv.writer(buf)
    writer.writerow(
        [
            "run_id",
            "period_start",
            "period_end",
            "staff_id",
            "source_type",
            "source_id",
            "base_amount",
            "commission_amount",
            "rule_id",
            "created_at",
        ]
    )
    for e in entries:
        writer.writerow(
            [
                str(getattr(run, "id", "")),
                run.period_start.isoformat() if getattr(run, "period_start", None) else "",
                run.period_end.isoformat() if getattr(run, "period_end", None) else "",
                str(getattr(e, "staff_id", "")),
                getattr(e, "source_type", ""),
                getattr(e, "source_id", ""),
                str(getattr(e, "base_amount", "")),
                str(getattr(e, "commission_amount", "")),
                str(getattr(e, "rule_id", "") or ""),
                e.created_at.isoformat() if getattr(e, "created_at", None) else "",
            ]
        )
    return buf.getvalue()
