"""Unit tests for subscription health scoring.

Tests app.services.subscription_health pure functions only.
No database required.

Score formula (base 35):
  +20  logins_last_7d   (min(v,7)/7 * 20)
  +15  logins_last_30d  (min(v,30)/30 * 15)
  +15  feature_diversity (min(v,10)/10 * 15)
  +10  onboarding_complete
  +15  last_nps_score   (score/10 * 15)
  +10  support_sentiment (+10 * sentiment, clamped to [-1,1])
  -10  days_since_last_invoice > 30
  -20  per failed_payment (capped at -40)
  -10  approaching_limits
  → clamped to [0, 100]

Risk levels:
  >= 80 → healthy
  50–79 → at_risk
  < 50  → critical
"""
from __future__ import annotations

import pytest
from app.services.subscription_health import HealthFactors, calculate_health_score


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def score_of(factors: HealthFactors) -> int:
    score, _ = calculate_health_score(factors)
    return score


def risk_of(factors: HealthFactors) -> str:
    _, risk = calculate_health_score(factors)
    return risk


# ─────────────────────────────────────────────────────────────────────────────
# Risk level tests
# ─────────────────────────────────────────────────────────────────────────────

def test_all_max_factors_healthy():
    """Max possible inputs → score >= 80 and healthy."""
    f = HealthFactors(
        logins_last_7d=7,
        logins_last_30d=30,
        feature_diversity=10,
        onboarding_complete=True,
        last_nps_score=10,
        support_sentiment=1.0,
        days_since_last_invoice=0,
        failed_payments=0,
        approaching_limits=False,
    )
    s, risk = calculate_health_score(f)
    assert s >= 80
    assert risk == "healthy"


def test_default_factors_critical_or_at_risk():
    """HealthFactors() with no activity should NOT be healthy (base 35 < 80)."""
    # Default: days_since_last_invoice=999 → -10 penalty → base 25
    s, risk = calculate_health_score(HealthFactors())
    assert risk in ("critical", "at_risk")
    assert s < 80


def test_fully_active_user_healthy():
    """7 logins/7d, 30 logins/30d, 10 features, NPS=10, onboarded → >= 80."""
    f = HealthFactors(
        logins_last_7d=7,
        logins_last_30d=30,
        feature_diversity=10,
        onboarding_complete=True,
        last_nps_score=10,
        days_since_last_invoice=5,
    )
    s, risk = calculate_health_score(f)
    assert s >= 80
    assert risk == "healthy"


def test_failed_payments_reduce_score():
    """3 failed payments significantly reduces the score."""
    base = score_of(HealthFactors(days_since_last_invoice=5))
    penalised = score_of(HealthFactors(failed_payments=3, days_since_last_invoice=5))
    assert penalised < base


def test_approaching_limits_reduces_score():
    f_no = HealthFactors(days_since_last_invoice=5, approaching_limits=False)
    f_yes = HealthFactors(days_since_last_invoice=5, approaching_limits=True)
    assert score_of(f_yes) == score_of(f_no) - 10


def test_onboarding_complete_adds_10():
    f_no = HealthFactors(days_since_last_invoice=5, onboarding_complete=False)
    f_yes = HealthFactors(days_since_last_invoice=5, onboarding_complete=True)
    assert score_of(f_yes) == score_of(f_no) + 10


# ─────────────────────────────────────────────────────────────────────────────
# Weight verification
# ─────────────────────────────────────────────────────────────────────────────

def test_logins_last_7d_max_bonus():
    """logins_last_7d=7 gives +20 vs logins_last_7d=0."""
    base = score_of(HealthFactors(days_since_last_invoice=5))
    with_logins = score_of(HealthFactors(logins_last_7d=7, days_since_last_invoice=5))
    assert with_logins == base + 20


def test_logins_last_7d_zero_no_bonus():
    """logins_last_7d=0 gives no bonus."""
    f = HealthFactors(logins_last_7d=0, days_since_last_invoice=5)
    # Compare to a known baseline: base 35 - 0 login bonus = 35
    # (no other factors active)
    assert score_of(f) == 35


def test_logins_last_30d_max_bonus():
    """logins_last_30d=30 gives +15 vs logins_last_30d=0."""
    base = score_of(HealthFactors(days_since_last_invoice=5))
    with_logins = score_of(HealthFactors(logins_last_30d=30, days_since_last_invoice=5))
    assert with_logins == base + 15


def test_feature_diversity_max_bonus():
    """feature_diversity=10 gives +15."""
    base = score_of(HealthFactors(days_since_last_invoice=5))
    with_features = score_of(HealthFactors(feature_diversity=10, days_since_last_invoice=5))
    assert with_features == base + 15


def test_feature_diversity_zero_no_bonus():
    """feature_diversity=0 gives no bonus."""
    f = HealthFactors(feature_diversity=0, days_since_last_invoice=5)
    assert score_of(f) == 35


def test_failed_payments_1_reduces_by_20():
    """1 failed payment → -20."""
    base = score_of(HealthFactors(days_since_last_invoice=5))
    with_fail = score_of(HealthFactors(failed_payments=1, days_since_last_invoice=5))
    assert with_fail == base - 20


def test_failed_payments_3_capped_at_40():
    """3 failed payments → penalty capped at -40."""
    base = score_of(HealthFactors(days_since_last_invoice=5))
    with_fail = score_of(HealthFactors(failed_payments=3, days_since_last_invoice=5))
    assert with_fail == max(0, base - 40)


def test_support_sentiment_negative_reduces():
    """support_sentiment=-1.0 → -10."""
    base = score_of(HealthFactors(days_since_last_invoice=5))
    negative = score_of(HealthFactors(support_sentiment=-1.0, days_since_last_invoice=5))
    assert negative == base - 10


def test_support_sentiment_positive_adds():
    """support_sentiment=+1.0 → +10."""
    base = score_of(HealthFactors(days_since_last_invoice=5))
    positive = score_of(HealthFactors(support_sentiment=1.0, days_since_last_invoice=5))
    assert positive == base + 10


def test_nps_score_10_max_bonus():
    """last_nps_score=10 → +15."""
    base = score_of(HealthFactors(days_since_last_invoice=5))
    with_nps = score_of(HealthFactors(last_nps_score=10, days_since_last_invoice=5))
    assert with_nps == base + 15


def test_nps_score_0_no_bonus():
    """last_nps_score=0 → +0."""
    base = score_of(HealthFactors(days_since_last_invoice=5))
    with_nps = score_of(HealthFactors(last_nps_score=0, days_since_last_invoice=5))
    assert with_nps == base


def test_invoice_gap_over_30_reduces_by_10():
    """days_since_last_invoice=31 → -10 penalty."""
    no_gap = score_of(HealthFactors(days_since_last_invoice=5))
    with_gap = score_of(HealthFactors(days_since_last_invoice=31))
    assert with_gap == no_gap - 10


def test_invoice_gap_29_no_penalty():
    """days_since_last_invoice=29 → no penalty."""
    no_gap = score_of(HealthFactors(days_since_last_invoice=5))
    under_30 = score_of(HealthFactors(days_since_last_invoice=29))
    assert under_30 == no_gap


# ─────────────────────────────────────────────────────────────────────────────
# Risk level boundary tests
# ─────────────────────────────────────────────────────────────────────────────

def _make_score_exactly(target: int) -> str:
    """Return risk_level for a score that should land at exactly `target`.

    We craft factors that sum to exactly `target`:
    base=35, logins_7d contribution = target-35 clamped to [0,20].
    If target < 35, use negative factors.
    """
    delta = target - 35
    if delta >= 0:
        # Use logins bonus: delta = min(v/7)*20 → v = delta/20 * 7
        # Easier: just use feature_diversity + logins additively
        # delta must be achievable via onboarding (10) + feature_diversity pct
        # Use direct parameter injection via failing payments to lower score
        # Simplest: use logins_last_7d proportionally
        logins = round(delta / 20 * 7)  # gives approx delta from logins
        actual, risk = calculate_health_score(HealthFactors(
            logins_last_7d=logins,
            days_since_last_invoice=5,
        ))
        return risk
    else:
        # Use failed_payments to push below 35
        payments = min((-delta) // 20 + 1, 2)
        actual, risk = calculate_health_score(HealthFactors(
            failed_payments=payments,
            days_since_last_invoice=5,
        ))
        return risk


def test_score_80_is_healthy():
    """Score exactly 80 → healthy."""
    # 35 base + 20 (logins 7d max) + 15 (logins 30d max) + 10 (onboarding) = 80
    f = HealthFactors(
        logins_last_7d=7,
        logins_last_30d=30,
        onboarding_complete=True,
        days_since_last_invoice=5,
    )
    s, risk = calculate_health_score(f)
    assert s == 80
    assert risk == "healthy"


def test_score_79_is_at_risk():
    """Score exactly 79 → at_risk."""
    # 35 + 20 + 15 + 10 = 80 → reduce by 1 using partial logins_30d
    # 35 + 20 + 14 + 10 = 79 (logins_30d=28 → 28/30*15 = 14)
    f = HealthFactors(
        logins_last_7d=7,
        logins_last_30d=28,
        onboarding_complete=True,
        days_since_last_invoice=5,
    )
    s, risk = calculate_health_score(f)
    assert s == 79
    assert risk == "at_risk"


def test_score_50_is_at_risk():
    """Score in 50-79 range → at_risk."""
    # 35 base + 15 (logins 30d max) = 50
    f = HealthFactors(logins_last_30d=30, days_since_last_invoice=5)
    s, risk = calculate_health_score(f)
    assert s == 50
    assert risk == "at_risk"


def test_score_49_is_critical():
    """Score exactly 49 → critical."""
    # 35 base + 15 (logins 30d) - 1 not achievable cleanly;
    # use: 35 base, no logins, approaching_limits → 35-10=25 → too low
    # 35 + logins_7d partial to get 49:
    # 49 - 35 = 14 from logins_7d: 14/20*7 = 4.9 → 5 logins → 5/7*20 = 14.3 → rounds to 14
    f = HealthFactors(logins_last_7d=5, days_since_last_invoice=5)
    s, risk = calculate_health_score(f)
    # score = 35 + round(5/7*20) = 35 + 14 = 49
    assert s == 49
    assert risk == "critical"


# ─────────────────────────────────────────────────────────────────────────────
# Score clamping
# ─────────────────────────────────────────────────────────────────────────────

def test_extreme_negative_score_clamped_to_zero():
    """Extreme negative factors → score >= 0."""
    f = HealthFactors(
        failed_payments=10,
        approaching_limits=True,
        support_sentiment=-1.0,
        days_since_last_invoice=999,
    )
    s, _ = calculate_health_score(f)
    assert s >= 0


def test_all_max_score_clamped_to_100():
    """All-max factors → score <= 100."""
    f = HealthFactors(
        logins_last_7d=100,
        logins_last_30d=100,
        feature_diversity=100,
        onboarding_complete=True,
        last_nps_score=10,
        support_sentiment=1.0,
        days_since_last_invoice=0,
        failed_payments=0,
        approaching_limits=False,
    )
    s, _ = calculate_health_score(f)
    assert s <= 100


# ─────────────────────────────────────────────────────────────────────────────
# Determinism
# ─────────────────────────────────────────────────────────────────────────────

def test_same_inputs_produce_same_output():
    """calculate_health_score is deterministic."""
    f = HealthFactors(logins_last_7d=3, logins_last_30d=10, feature_diversity=5,
                      failed_payments=1, days_since_last_invoice=20)
    r1 = calculate_health_score(f)
    r2 = calculate_health_score(f)
    assert r1 == r2


def test_changing_one_field_changes_score():
    """Changing a single factor changes the score predictably."""
    base = HealthFactors(logins_last_7d=0, days_since_last_invoice=5)
    changed = HealthFactors(logins_last_7d=7, days_since_last_invoice=5)
    assert score_of(changed) > score_of(base)
