"""Unit tests for NPS survey pure helpers.

Tests app.services.nps pure functions only. No database required.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
import pytest
from app.services.nps import categorize_score, calculate_nps, should_trigger_nps


# ─────────────────────────────────────────────────────────────────────────────
# categorize_score
# ─────────────────────────────────────────────────────────────────────────────

def test_categorize_score_0_is_detractor():
    assert categorize_score(0) == "detractor"


def test_categorize_score_6_is_detractor():
    assert categorize_score(6) == "detractor"


def test_categorize_score_7_is_passive():
    assert categorize_score(7) == "passive"


def test_categorize_score_8_is_passive():
    assert categorize_score(8) == "passive"


def test_categorize_score_9_is_promoter():
    assert categorize_score(9) == "promoter"


def test_categorize_score_10_is_promoter():
    assert categorize_score(10) == "promoter"


def test_categorize_score_negative_raises():
    with pytest.raises(ValueError):
        categorize_score(-1)


def test_categorize_score_11_raises():
    with pytest.raises(ValueError):
        categorize_score(11)


@pytest.mark.parametrize("score", list(range(11)))
def test_categorize_all_scores_return_valid_category(score):
    result = categorize_score(score)
    assert result in ("promoter", "passive", "detractor")


# ─────────────────────────────────────────────────────────────────────────────
# calculate_nps
# ─────────────────────────────────────────────────────────────────────────────

def test_calculate_nps_empty_list():
    assert calculate_nps([]) == 0


def test_calculate_nps_all_promoters():
    # 3 promoters, 0 detractors → 100
    assert calculate_nps([9, 10, 10]) == 100


def test_calculate_nps_all_detractors():
    # 0 promoters, 3 detractors → -100
    assert calculate_nps([0, 1, 2]) == -100


def test_calculate_nps_equal_promoters_and_detractors():
    # e.g. [10, 0] → 50% - 50% = 0
    assert calculate_nps([10, 0]) == 0


def test_calculate_nps_mixed():
    # [10, 10, 7, 3]: promoters=2/4=50%, detractors=1/4=25% → 25
    assert calculate_nps([10, 10, 7, 3]) == 25


def test_calculate_nps_single_promoter():
    assert calculate_nps([9]) == 100


def test_calculate_nps_single_detractor():
    assert calculate_nps([6]) == -100


def test_calculate_nps_in_bounds():
    import random
    scores = [random.randint(0, 10) for _ in range(100)]
    result = calculate_nps(scores)
    assert -100 <= result <= 100


def test_calculate_nps_two_promoters_one_passive():
    # [10, 9, 7]: promoters=2/3≈66.7%, detractors=0 → round(66.7) = 67
    result = calculate_nps([10, 9, 7])
    assert result == 67


# ─────────────────────────────────────────────────────────────────────────────
# should_trigger_nps
# ─────────────────────────────────────────────────────────────────────────────

_NOW = datetime(2026, 5, 2, 12, 0, 0, tzinfo=timezone.utc)


def _days_ago(n: int) -> datetime:
    return _NOW - timedelta(days=n)


def test_day30_exactly_30_days_no_prior():
    assert should_trigger_nps(
        survey_type="day_30",
        first_paid_at=_days_ago(30),
        now=_NOW,
    ) is True


def test_day30_28_days_ago_in_window():
    assert should_trigger_nps(
        survey_type="day_30",
        first_paid_at=_days_ago(28),
        now=_NOW,
    ) is True


def test_day30_27_days_ago_too_early():
    assert should_trigger_nps(
        survey_type="day_30",
        first_paid_at=_days_ago(27),
        now=_NOW,
    ) is False


def test_day30_33_days_ago_past_window():
    assert should_trigger_nps(
        survey_type="day_30",
        first_paid_at=_days_ago(33),
        now=_NOW,
    ) is False


def test_day30_recent_trigger_blocks():
    # first_paid 30 days ago but last triggered only 10 days ago → False
    assert should_trigger_nps(
        survey_type="day_30",
        first_paid_at=_days_ago(30),
        last_triggered_at=_days_ago(10),
        now=_NOW,
    ) is False


def test_day90_exactly_90_days_no_prior():
    assert should_trigger_nps(
        survey_type="day_90",
        first_paid_at=_days_ago(90),
        now=_NOW,
    ) is True


def test_day90_88_days_in_window():
    assert should_trigger_nps(
        survey_type="day_90",
        first_paid_at=_days_ago(88),
        now=_NOW,
    ) is True


def test_day90_87_days_too_early():
    assert should_trigger_nps(
        survey_type="day_90",
        first_paid_at=_days_ago(87),
        now=_NOW,
    ) is False


def test_cancellation_always_true():
    assert should_trigger_nps(
        survey_type="cancellation",
        first_paid_at=_days_ago(5),
        last_triggered_at=_days_ago(1),
        now=_NOW,
    ) is True


def test_cancellation_true_without_any_dates():
    assert should_trigger_nps(survey_type="cancellation", now=_NOW) is True


def test_quarterly_enterprise_no_prior():
    assert should_trigger_nps(
        survey_type="quarterly",
        plan="enterprise",
        now=_NOW,
    ) is True


def test_quarterly_starter_plan_false():
    assert should_trigger_nps(
        survey_type="quarterly",
        plan="starter",
        now=_NOW,
    ) is False


def test_quarterly_enterprise_85_days_ago_false():
    # 85 days < 80 threshold — wait: 85 > 80, so True. Let's make it 79 days.
    # spec says last_triggered 85 days ago → False (within 90 days)
    # Our service uses _QUARTERLY_MIN_DAYS = 80, so 85 > 80 means True.
    # The spec test name says "85 days ago → False (within 90 days)".
    # We'll follow the spec description literally and set threshold to 90 for this check:
    # Actually, re-reading: the spec says last_triggered 85 days ago → False, 81 days → False, 91 days → True.
    # That implies the threshold is 90 days. Let me verify against our service:
    # _QUARTERLY_MIN_DAYS = 80 would make 85 days True.
    # We need to match the spec: threshold must be 90. Update service accordingly.
    # For now, test against the spec semantics.
    assert should_trigger_nps(
        survey_type="quarterly",
        plan="enterprise",
        last_triggered_at=_days_ago(85),
        now=_NOW,
    ) is False


def test_quarterly_enterprise_81_days_ago_false():
    assert should_trigger_nps(
        survey_type="quarterly",
        plan="enterprise",
        last_triggered_at=_days_ago(81),
        now=_NOW,
    ) is False


def test_quarterly_enterprise_91_days_ago_true():
    assert should_trigger_nps(
        survey_type="quarterly",
        plan="enterprise",
        last_triggered_at=_days_ago(91),
        now=_NOW,
    ) is True
