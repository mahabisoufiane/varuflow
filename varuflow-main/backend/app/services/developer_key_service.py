"""API developer-key service (Item 45).

Pure helpers handle key generation, hashing, scope checks, and
usage-log trim arithmetic. DB-bound helpers handle key lookup and
the usage-log prune-on-insert.

Key format: ``vk_<prefix8>_<secret32>``

* ``vk_`` — Varuflow key, distinct from JWTs so the auth middleware
  can fast-path between the two without a DB lookup on JWTs.
* ``prefix8`` — first 8 chars of the secret. Indexed (unique) so the
  request-time lookup is one index hit. Surfaced in the UI as the
  human-readable identifier.
* ``secret32`` — 32-char URL-safe random suffix. SHA-256 of the
  full ``prefix8 + secret32`` is stored in ``key_hash``.

The plaintext is returned to the operator exactly once at creation
time and never again — losing it forces a rotation, which is the
documented hardening posture.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets as _secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable


# ═══════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════


KEY_PREFIX_TAG = "vk_"        # "Varuflow key" — distinct from JWTs.
KEY_PREFIX_LEN = 8            # Random prefix length (URL-safe alphabet).
KEY_SECRET_LEN = 32           # Suffix length.
USAGE_LOG_LIMIT = 100         # Max rows kept per key.

# Scope hierarchy. Higher tiers grant everything below them so a
# single ``admin`` scope is sufficient for read+write+admin paths.
ALLOWED_SCOPES: tuple[str, ...] = ("read", "write", "admin")
_SCOPE_RANK = {"read": 0, "write": 1, "admin": 2}


class ApiKeyValidationError(ValueError):
    """Raised when an API-key input fails validation."""


# ═══════════════════════════════════════════════════════════════════
# Pure validators / generators
# ═══════════════════════════════════════════════════════════════════


def validate_name(name: str) -> str:
    if not isinstance(name, str):
        raise ApiKeyValidationError("name_required")
    cleaned = name.strip()
    if not cleaned:
        raise ApiKeyValidationError("name_empty")
    if len(cleaned) > 120:
        raise ApiKeyValidationError("name_too_long")
    return cleaned


def validate_scopes(scopes: Iterable[str]) -> list[str]:
    """Normalise + validate the requested scopes.

    Lower-cases, deduplicates, and refuses unknown scopes. An empty
    list is rejected — every key must carry at least ``read`` so a
    revoked-but-still-cached key never silently gains access on a
    rename.
    """
    out: list[str] = []
    seen: set[str] = set()
    for raw in scopes or []:
        if not isinstance(raw, str):
            continue
        s = raw.strip().lower()
        if not s or s in seen:
            continue
        if s not in ALLOWED_SCOPES:
            raise ApiKeyValidationError(f"scope_rejected:{s}")
        seen.add(s)
        out.append(s)
    if not out:
        raise ApiKeyValidationError("scope_required")
    return out


def has_scope(granted: Iterable[str], required: str) -> bool:
    """Hierarchical check: ``admin`` covers ``write`` covers ``read``."""
    if required not in _SCOPE_RANK:
        return False
    needed_rank = _SCOPE_RANK[required]
    for g in granted or []:
        if g in _SCOPE_RANK and _SCOPE_RANK[g] >= needed_rank:
            return True
    return False


# ─── Key generation ─────────────────────────────────────────────────


@dataclass
class GeneratedKey:
    """Output of :func:`generate_key` — the only point at which the
    plaintext exists in process memory. Callers persist ``prefix`` +
    ``hash`` and return ``plaintext`` to the user once."""
    plaintext: str
    prefix: str
    hash: str

    def as_persist(self) -> dict:
        return {"key_prefix": self.prefix, "key_hash": self.hash}


def _random_token(length: int) -> str:
    """URL-safe random token of exactly ``length`` chars."""
    # ``secrets.token_urlsafe`` returns roughly ``length * 4/3`` chars
    # of entropy. Generate a bit more then slice to the exact length
    # so the prefix index column has a stable width.
    raw = _secrets.token_urlsafe(length * 2)
    # Strip ``-`` and ``_`` to keep prefixes copy-paste-friendly in
    # CLI flags. Plenty of entropy remains.
    cleaned = "".join(c for c in raw if c.isalnum())
    return cleaned[:length]


def generate_key() -> GeneratedKey:
    prefix = _random_token(KEY_PREFIX_LEN)
    secret = _random_token(KEY_SECRET_LEN)
    plaintext = f"{KEY_PREFIX_TAG}{prefix}_{secret}"
    digest = hash_key(plaintext)
    return GeneratedKey(plaintext=plaintext, prefix=prefix, hash=digest)


def hash_key(plaintext: str) -> str:
    """SHA-256 hex digest. The secrets are 256-bit random, so a
    cryptographic password hash (argon2 etc.) buys nothing — the
    cost would only slow legitimate request-time verification.
    """
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def parse_key(plaintext: str) -> tuple[str, str]:
    """Split a presented key into ``(prefix, full_plaintext)``.

    Refuses anything missing the ``vk_`` tag or the dot separator
    so a JWT (which never starts with ``vk_``) is rejected fast.
    """
    if not isinstance(plaintext, str):
        raise ApiKeyValidationError("key_invalid")
    if not plaintext.startswith(KEY_PREFIX_TAG):
        raise ApiKeyValidationError("key_invalid")
    body = plaintext[len(KEY_PREFIX_TAG):]
    if "_" not in body:
        raise ApiKeyValidationError("key_invalid")
    prefix, _ = body.split("_", 1)
    if len(prefix) != KEY_PREFIX_LEN:
        raise ApiKeyValidationError("key_invalid")
    return prefix, plaintext


def verify_key(plaintext: str, expected_hash: str) -> bool:
    """Constant-time hash comparison to defeat timing attacks."""
    return hmac.compare_digest(hash_key(plaintext), expected_hash)


# ─── Expiry ─────────────────────────────────────────────────────────


def is_expired(expires_at: datetime | None, *, now: datetime | None = None) -> bool:
    if expires_at is None:
        return False
    moment = now or datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= moment


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════════════
# DB-bound layer
# ═══════════════════════════════════════════════════════════════════


async def lookup_active_key(db, *, prefix: str):
    """Return the ApiKey row matching ``prefix`` if it's still active.

    Returns ``None`` if missing, revoked, or expired so callers can
    short-circuit on a single boolean check.
    """
    from sqlalchemy import select as _select

    from app.features.integrations.developer_models import ApiKey

    row = await db.scalar(
        _select(ApiKey).where(ApiKey.key_prefix == prefix)
    )
    if row is None or row.is_revoked or is_expired(row.expires_at):
        return None
    return row


async def record_usage(
    db,
    *,
    key_id: uuid.UUID,
    method: str,
    path: str,
    status_code: int | None,
    ip: str | None,
) -> None:
    """Append a usage row and prune to the most recent
    :data:`USAGE_LOG_LIMIT` entries for this key."""
    from sqlalchemy import delete as _delete, select as _select

    from app.features.integrations.developer_models import ApiKey, ApiKeyUsage

    db.add(
        ApiKeyUsage(
            id=uuid.uuid4(),
            key_id=key_id,
            method=method[:10],
            path=path[:500],
            status_code=status_code,
            ip=ip[:64] if ip else None,
        )
    )
    # Update last_used_at so the UI can highlight stale keys.
    key_row = await db.get(ApiKey, key_id)
    if key_row is not None:
        key_row.last_used_at = now_utc()
    # Trim oldest rows beyond the cap. Single window query keeps
    # this O(log n).
    keep_ids = (
        await db.execute(
            _select(ApiKeyUsage.id)
            .where(ApiKeyUsage.key_id == key_id)
            .order_by(ApiKeyUsage.called_at.desc())
            .limit(USAGE_LOG_LIMIT)
        )
    ).scalars().all()
    if keep_ids:
        await db.execute(
            _delete(ApiKeyUsage)
            .where(ApiKeyUsage.key_id == key_id)
            .where(ApiKeyUsage.id.notin_(keep_ids))
        )


async def revoke_all_for_org(db, *, org_id: uuid.UUID) -> int:
    """Bulk revoke every key for an org. Used by the GDPR erasure
    flow (so the API surface is closed even before cascade) and by
    the offboarding script."""
    from sqlalchemy import update as _update

    from app.features.integrations.developer_models import ApiKey

    result = await db.execute(
        _update(ApiKey)
        .where(ApiKey.org_id == org_id, ApiKey.is_revoked == False)  # noqa: E712
        .values(is_revoked=True)
    )
    return result.rowcount or 0
