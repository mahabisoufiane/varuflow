"""Symmetric encryption helpers for secrets stored at rest.

Used to encrypt third-party OAuth tokens (e.g. Fortnox access/refresh tokens)
before writing them to the database. An attacker with a read-only DB dump
should not be able to impersonate the customer against the upstream API.

Key management
--------------
Set ``FORTNOX_ENCRYPTION_KEY`` in Railway Variables to a urlsafe base64
Fernet key. Generate one with::

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

If the key is not configured, encryption is a no-op (plaintext pass-through).
Existing plaintext tokens in the DB are decrypted transparently on read, so
rolling out encryption is zero-downtime.

Ciphertext format
-----------------
``fenc:v1:<urlsafe-base64 Fernet token>``

The prefix lets us distinguish ciphertext from legacy plaintext values and
lets us rotate the scheme later (``fenc:v2:…``) without a data migration.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.config import settings

log = logging.getLogger(__name__)

_PREFIX = "fenc:v1:"

try:
    from cryptography.fernet import Fernet, InvalidToken
    _CRYPTO_AVAILABLE = True
except Exception:  # pragma: no cover — cryptography is a hard dep of python-jose
    _CRYPTO_AVAILABLE = False
    Fernet = None  # type: ignore
    InvalidToken = Exception  # type: ignore


_fernet: "Optional[Fernet]" = None


def _get_fernet() -> "Optional[Fernet]":
    """Return a cached Fernet instance, or None if encryption is disabled."""
    global _fernet
    if _fernet is not None:
        return _fernet
    if not _CRYPTO_AVAILABLE:
        return None
    key = getattr(settings, "FORTNOX_ENCRYPTION_KEY", "") or ""
    if not key:
        return None
    try:
        _fernet = Fernet(key.encode("utf-8") if isinstance(key, str) else key)
        return _fernet
    except Exception as exc:  # invalid key format
        log.error("FORTNOX_ENCRYPTION_KEY is invalid — storing tokens in plaintext: %s", exc)  # nosemgrep: python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure
        return None


def encrypt_token(plaintext: Optional[str]) -> Optional[str]:
    """Encrypt a secret for storage. Returns plaintext unchanged if encryption
    is disabled. Safe to call with None."""
    if plaintext is None or plaintext == "":
        return plaintext
    # Already encrypted — don't double-wrap
    if plaintext.startswith(_PREFIX):
        return plaintext
    f = _get_fernet()
    if f is None:
        return plaintext
    token = f.encrypt(plaintext.encode("utf-8")).decode("utf-8")
    return f"{_PREFIX}{token}"


def decrypt_token(value: Optional[str]) -> Optional[str]:
    """Decrypt a secret read from storage. Legacy plaintext values pass through
    unchanged so the rollout is zero-downtime. Safe to call with None."""
    if value is None or value == "":
        return value
    if not value.startswith(_PREFIX):
        # Legacy plaintext — leave as-is
        return value
    f = _get_fernet()
    if f is None:
        # Key removed after data was encrypted — surface the problem loudly
        log.error("Encountered encrypted token but FORTNOX_ENCRYPTION_KEY is not configured")
        raise RuntimeError("FORTNOX_ENCRYPTION_KEY missing — cannot decrypt stored token")
    try:
        return f.decrypt(value[len(_PREFIX):].encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        log.error("Fernet decryption failed — key may have been rotated: %s", exc)
        raise RuntimeError("Stored token could not be decrypted (key mismatch)") from exc
