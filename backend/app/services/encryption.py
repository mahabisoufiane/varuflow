"""Application-level PII encryption helpers (Item 28).

This module is the general-purpose successor to ``crypto.py`` (which is
still used for Fortnox OAuth tokens — kept as-is to avoid re-wiring a
paid-path integration for a refactor). ``encryption.py`` provides:

  • ``encrypt_pii`` / ``decrypt_pii`` — pure helpers mirroring the
    ``crypto.encrypt_token`` / ``decrypt_token`` contract so both
    subsystems behave identically to an auditor.
  • ``EncryptedString`` — a SQLAlchemy ``TypeDecorator`` that wraps a
    column so ORM writes encrypt transparently and ORM reads decrypt
    transparently. Legacy plaintext rows are returned unchanged so a
    rollout can proceed without a data migration.

Key management
--------------
Set ``PII_ENCRYPTION_KEY`` in the environment to a urlsafe base64 Fernet
key (32 bytes). Generate one with::

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

During rotation, set ``PII_ENCRYPTION_KEY_PREVIOUS`` to the previous key
so in-flight rows encrypted with it still decrypt. ``MultiFernet`` uses
the first key in the list for encryption and tries each key in order
for decryption — new writes automatically pick up the new key while old
rows remain readable.

If ``PII_ENCRYPTION_KEY`` is empty the module is a no-op (plaintext
pass-through on both directions). This matches ``crypto.py`` and keeps
local dev boxes working without forcing developers to generate a key
they will then have to remember to purge from their shells.

Ciphertext format
-----------------
``penc:v1:<urlsafe-base64 Fernet token>``

The ``penc:`` prefix (P for PII) is distinct from ``fenc:`` (F for
Fortnox) so a migration that copies a Fortnox-encrypted value into a
PII column would fail loudly instead of silently being returned as
plaintext. The ``v1`` allows a future scheme swap (AES-GCM with AAD,
hardware-KMS-backed envelope keys, etc.) without a data migration.

Not a full-disk encryption substitute
-------------------------------------
Application-level column encryption defends against a specific threat:
a read-only database snapshot (backup leak, stolen replica, compromised
BI tool). It does NOT protect against an attacker with RCE on the API
server — the process has the key in memory by definition. For that
class of attack, combine this with transparent disk encryption on the
Postgres host and strict IAM on the backup bucket.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.types import String, TypeDecorator

from app.config import settings

log = logging.getLogger(__name__)

_PREFIX = "penc:v1:"

try:
    from cryptography.fernet import Fernet, InvalidToken, MultiFernet
    _CRYPTO_AVAILABLE = True
except Exception:  # pragma: no cover — cryptography is a hard dep of python-jose
    _CRYPTO_AVAILABLE = False
    Fernet = None  # type: ignore
    InvalidToken = Exception  # type: ignore
    MultiFernet = None  # type: ignore


_cipher: "Optional[MultiFernet]" = None
_cipher_loaded: bool = False


def _get_cipher() -> "Optional[MultiFernet]":
    """Return a cached MultiFernet or None if encryption is disabled.

    Called on every ``encrypt_pii`` / ``decrypt_pii`` invocation; the
    cache avoids re-constructing the Fernet on every row.
    """
    global _cipher, _cipher_loaded
    if _cipher_loaded:
        return _cipher
    _cipher_loaded = True  # Set first so failures don't retry on every call.
    if not _CRYPTO_AVAILABLE:
        return None

    primary = (getattr(settings, "PII_ENCRYPTION_KEY", "") or "").strip()
    if not primary:
        return None

    keys = [primary]
    previous = (getattr(settings, "PII_ENCRYPTION_KEY_PREVIOUS", "") or "").strip()
    if previous:
        keys.append(previous)

    try:
        ferns = [Fernet(k.encode("utf-8") if isinstance(k, str) else k) for k in keys]
        _cipher = MultiFernet(ferns)
        return _cipher
    except Exception as exc:
        log.error("PII_ENCRYPTION_KEY is invalid — storing PII in plaintext: %s", exc)
        return None


def _reset_cache_for_tests() -> None:
    """Clear the cached cipher so a test can swap keys mid-run.

    Production code must never call this — the cache invalidation would
    race with concurrent requests. Wrapped in a leading underscore so
    linters flag accidental external use.
    """
    global _cipher, _cipher_loaded
    _cipher = None
    _cipher_loaded = False


def encrypt_pii(plaintext: Optional[str]) -> Optional[str]:
    """Encrypt a PII string for storage.

    • ``None`` → ``None`` (passes through so nullable columns work).
    • Empty string → empty string (don't encrypt an empty value — it
      would round-trip to an unreadable ciphertext and pollute indexes).
    • Already-prefixed ciphertext → returned unchanged (idempotent; a
      caller that runs the helper twice does not double-wrap).
    • No key configured → plaintext passes through (feature disabled).
    """
    if plaintext is None or plaintext == "":
        return plaintext
    if plaintext.startswith(_PREFIX):
        return plaintext
    cipher = _get_cipher()
    if cipher is None:
        return plaintext
    token = cipher.encrypt(plaintext.encode("utf-8")).decode("utf-8")
    return f"{_PREFIX}{token}"


def decrypt_pii(value: Optional[str]) -> Optional[str]:
    """Decrypt a PII string read from storage.

    • ``None`` / empty → returned unchanged.
    • Legacy plaintext (no prefix) → returned unchanged so a rollout
      over existing rows is zero-downtime.
    • Prefixed ciphertext → decrypted; on failure raises
      ``RuntimeError`` so a key-mismatch surfaces loudly rather than
      silently returning garbage.
    """
    if value is None or value == "":
        return value
    if not value.startswith(_PREFIX):
        return value  # Legacy plaintext.
    cipher = _get_cipher()
    if cipher is None:
        log.error("Encountered encrypted PII but PII_ENCRYPTION_KEY is not configured")
        raise RuntimeError("PII_ENCRYPTION_KEY missing — cannot decrypt stored PII")
    try:
        return cipher.decrypt(value[len(_PREFIX):].encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        log.error("PII decryption failed — key may have been rotated out: %s", exc)
        raise RuntimeError("Stored PII could not be decrypted (key mismatch)") from exc


class EncryptedString(TypeDecorator):
    """SQLAlchemy column type that transparently encrypts/decrypts strings.

    Usage::

        email: Mapped[str | None] = mapped_column(EncryptedString(512))

    The underlying DB column is ``VARCHAR(length)`` — use a size that
    accommodates the ciphertext, which is roughly
    ``len(_PREFIX) + ceil(plaintext_len / 3) * 4 + ~100`` bytes of
    Fernet overhead. A safe rule of thumb is ``2 * plaintext_max + 200``.

    Queries that filter on the column (``WHERE email = :x``) still work
    **only for exact matches on newly-written rows** because Fernet is
    non-deterministic: encrypting the same plaintext twice produces two
    different ciphertexts. For lookup-by-email we keep a non-encrypted
    hashed column (e.g. ``email_hash``) — not introduced in Item 28
    because no current query path requires it.
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):  # type: ignore[override]
        return encrypt_pii(value)

    def process_result_value(self, value, dialect):  # type: ignore[override]
        return decrypt_pii(value)
