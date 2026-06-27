"""Pure helpers for the referral program (Item 68).

Covers:
* referral-code generation (short, unambiguous, crypto-random),
* referral claim validation (self-referral rejection, code match,
  referee de-duplication),
* the status state machine PENDING → QUALIFIED → REWARDED
  (plus terminal REJECTED),
* reward computation.
"""
from __future__ import annotations

import re
import secrets
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

# Upper-case alphanumeric, minus the visually confusable glyphs
# (O/0, I/1, L) so operators can dictate codes on the phone.
CODE_ALPHABET: str = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH:   int = 8
MAX_TRIES:     int = 16

_CODE_RE = re.compile(rf"^[{CODE_ALPHABET}]{{{CODE_LENGTH}}}$")

ALLOWED_STATUSES: frozenset[str] = frozenset({
    "PENDING", "QUALIFIED", "REWARDED", "REJECTED",
})
_TRANSITIONS: dict[str, frozenset[str]] = {
    "PENDING":   frozenset({"QUALIFIED", "REJECTED"}),
    "QUALIFIED": frozenset({"REWARDED", "REJECTED"}),
    "REWARDED":  frozenset(),
    "REJECTED":  frozenset(),
}

MIN_REWARD: Decimal = Decimal("0.01")
MAX_REWARD: Decimal = Decimal("100000")

_Q2 = Decimal("0.01")


def generate_code(existing: set[str]) -> str:
    """Return a new 8-char code not present in ``existing``.

    Raises ``RuntimeError`` after ``MAX_TRIES`` consecutive collisions
    — with a ~30^8 alphabet that signals the caller passed a broken
    set, not that we've actually run out of codes.
    """
    for _ in range(MAX_TRIES):
        candidate = "".join(
            secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH)
        )
        if candidate not in existing:
            return candidate
    raise RuntimeError("could not generate a unique referral code")


def normalise_code(code: str) -> str:
    if not isinstance(code, str):
        raise ValueError("code must be a string")
    stripped = code.strip().upper().replace(" ", "").replace("-", "")
    if not _CODE_RE.match(stripped):
        raise ValueError(
            f"code must be {CODE_LENGTH} chars from {CODE_ALPHABET}"
        )
    return stripped


def validate_claim(
    *,
    referrer_id: str,
    referee_id:  str,
    existing_referees: Iterable[str],
) -> None:
    """Run the non-ORM rules before opening a referral."""
    if referrer_id == referee_id:
        raise ValueError("self-referral is not allowed")
    if referee_id in set(existing_referees):
        raise ValueError("referee has already been claimed")


def assert_transition(current: str, target: str) -> None:
    if current not in ALLOWED_STATUSES:
        raise ValueError(f"unknown source status: {current}")
    if target not in ALLOWED_STATUSES:
        raise ValueError(f"unknown target status: {target}")
    if target not in _TRANSITIONS[current]:
        raise ValueError(f"cannot transition {current} → {target}")


def validate_reward_amount(value) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("reward_amount must be a number")
    try:
        v = value if isinstance(value, Decimal) else Decimal(str(value))
    except Exception:
        raise ValueError("reward_amount must be a number")
    if v < MIN_REWARD:
        raise ValueError(f"reward_amount must be at least {MIN_REWARD}")
    if v > MAX_REWARD:
        raise ValueError(f"reward_amount exceeds {MAX_REWARD}")
    return v.quantize(_Q2, rounding=ROUND_HALF_UP)


def compute_reward(
    invoice_total: Decimal,
    *,
    percent: Decimal | None = None,
    flat:    Decimal | None = None,
    cap:     Decimal | None = None,
) -> Decimal:
    """Compute the referrer's reward from the referee's first paid invoice.

    Exactly one of ``percent`` or ``flat`` must be supplied. A ``cap``
    (if given) clips the result. Always returned rounded to cents.
    """
    if (percent is None) == (flat is None):
        raise ValueError("exactly one of percent or flat is required")
    if percent is not None:
        if percent <= 0 or percent > Decimal("100"):
            raise ValueError("percent must be in (0, 100]")
        reward = (invoice_total * percent / Decimal("100"))
    else:
        reward = flat  # type: ignore[assignment]
        if reward <= 0:
            raise ValueError("flat must be positive")
    if cap is not None and cap > 0 and reward > cap:
        reward = cap
    if reward < 0:
        reward = Decimal("0")
    return reward.quantize(_Q2, rounding=ROUND_HALF_UP)
