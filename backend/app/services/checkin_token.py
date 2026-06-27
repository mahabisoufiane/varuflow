"""Pure helpers for self-service booking check-in (Item 58).

Why separate from the router:

* Token generation, hashing and verification are sensitive —
  isolating them lets tests cover edge cases (expired, already-used,
  wrong shape, too-early check-in) without fixtures.
* The router stays thin: mint, verify, stamp.

Security
--------
* Plaintext token is a 32-byte URL-safe random string. Only the
  SHA-256 hash goes to the DB, matching the pattern in
  :mod:`app.services.portal_otp` and ``customer_portal_tokens``.
* Verification is a constant-time hash comparison via ``hmac.compare_digest``.
* Tokens default to 2 hours of validity and are rejected outside
  ``[appointment_start − 4h, appointment_end + 2h]`` so a leaked
  link for tomorrow's 09:00 booking can't be replayed today.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

# Token lifetime. Short enough that a phished link expires quickly,
# long enough that a pre-sent reminder (e.g. 1 h before) still works.
DEFAULT_TOKEN_TTL: timedelta = timedelta(hours=2)

# Window around appointment_start when check-in is allowed. Tunable
# by the caller but bounded here so accidental reuse is caught.
EARLY_CHECKIN_WINDOW: timedelta = timedelta(hours=4)
LATE_CHECKIN_WINDOW: timedelta = timedelta(hours=2)

TOKEN_BYTES: int = 32
TOKEN_HASH_HEX_LEN: int = 64  # sha256 hex digest length


@dataclass(frozen=True)
class MintedToken:
    """Result of :func:`mint_token` — give ``plaintext`` to the
    customer, persist ``token_hash`` + ``expires_at`` in the DB."""
    plaintext:  str
    token_hash: str
    expires_at: datetime


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_token(token: str) -> str:
    """Public wrapper — routers should not import `_hash` directly."""
    if not token:
        raise ValueError("token must be non-empty")
    return _hash(token)


def mint_token(*, now: datetime, ttl: timedelta = DEFAULT_TOKEN_TTL) -> MintedToken:
    """Generate a new check-in token anchored at ``now``."""
    if ttl <= timedelta(0):
        raise ValueError("ttl must be positive")
    plaintext = secrets.token_urlsafe(TOKEN_BYTES)
    return MintedToken(
        plaintext=plaintext,
        token_hash=_hash(plaintext),
        expires_at=now + ttl,
    )


def verify_hash_matches(candidate_plaintext: str, stored_hash: str) -> bool:
    """Constant-time compare of the candidate's hash to ``stored_hash``."""
    if not candidate_plaintext or not stored_hash:
        return False
    if len(stored_hash) != TOKEN_HASH_HEX_LEN:
        return False
    return hmac.compare_digest(_hash(candidate_plaintext), stored_hash)


@dataclass(frozen=True)
class CheckinState:
    """Subset of :class:`AppointmentCheckinToken` + appointment needed
    for :func:`is_valid_now`."""
    expires_at:        datetime
    used_at:           datetime | None
    appointment_start: datetime
    appointment_end:   datetime


def is_valid_now(state: CheckinState, now: datetime) -> tuple[bool, str]:
    """True iff the token can be redeemed at ``now``.

    Returns ``(ok, reason)`` so the router can surface the specific
    failure back to the caller — useful for UX ("booking hasn't
    started yet") and analytics ("how often do guests reuse links").
    """
    if state.used_at is not None:
        return False, "already_used"
    if now >= state.expires_at:
        return False, "expired"
    # Reject way-too-early check-ins so a reminder sent the day before
    # can't flip the status 24 h ahead of time.
    if now + EARLY_CHECKIN_WINDOW < state.appointment_start:
        return False, "too_early"
    if now > state.appointment_end + LATE_CHECKIN_WINDOW:
        return False, "too_late"
    return True, "ok"
