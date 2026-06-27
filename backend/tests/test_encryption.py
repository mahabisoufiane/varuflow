"""Tests for the PII encryption helpers (Item 28).

Covers the pure helpers + the SQLAlchemy TypeDecorator. No Postgres is
required — TypeDecorator is tested by driving ``process_bind_param`` /
``process_result_value`` directly, the same codepath SQLAlchemy uses at
runtime.

The user spec referenced ``backend/app/tests/test_encryption.py`` but
existing repo convention (see ``backend/tests/test_*.py``) is to keep
tests next to ``conftest.py`` at ``backend/tests/``. Following the
convention keeps the discovery rules in ``pyproject.toml`` / pytest
unchanged.
"""
from __future__ import annotations

import importlib
import os
from typing import Iterator

import pytest
from cryptography.fernet import Fernet

from app.services import encryption as enc_mod


KEY_A = Fernet.generate_key().decode("utf-8")
KEY_B = Fernet.generate_key().decode("utf-8")


@pytest.fixture(autouse=True)
def _configure_key(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Load a deterministic key before every test and clear the cache.

    The module caches the MultiFernet on first use; without the reset,
    a later test that swaps the key would still get the stale cipher.
    """
    from app.config import settings as _settings
    monkeypatch.setattr(_settings, "PII_ENCRYPTION_KEY", KEY_A, raising=False)
    monkeypatch.setattr(_settings, "PII_ENCRYPTION_KEY_PREVIOUS", "", raising=False)
    enc_mod._reset_cache_for_tests()
    yield
    enc_mod._reset_cache_for_tests()


# ── Pure helper tests ────────────────────────────────────────────────────

def test_encrypt_none_passes_through():
    assert enc_mod.encrypt_pii(None) is None


def test_encrypt_empty_string_passes_through():
    # Empty string is falsy — encrypting it would produce a ~100-char
    # ciphertext for zero information gain and pollute indexes.
    assert enc_mod.encrypt_pii("") == ""


def test_decrypt_none_passes_through():
    assert enc_mod.decrypt_pii(None) is None


def test_decrypt_empty_string_passes_through():
    assert enc_mod.decrypt_pii("") == ""


def test_roundtrip_ascii():
    ct = enc_mod.encrypt_pii("alice@example.com")
    assert ct is not None
    assert ct.startswith("penc:v1:")
    assert enc_mod.decrypt_pii(ct) == "alice@example.com"


def test_roundtrip_unicode():
    plaintext = "Åsa Ekström • Storgatan 12, Göteborg"
    ct = enc_mod.encrypt_pii(plaintext)
    assert ct is not None and ct.startswith("penc:v1:")
    assert enc_mod.decrypt_pii(ct) == plaintext


def test_encrypt_is_non_deterministic():
    # Fernet includes a random IV — the same plaintext must not produce
    # the same ciphertext twice. Otherwise an attacker with DB read could
    # correlate rows by ciphertext equality.
    a = enc_mod.encrypt_pii("same-value")
    b = enc_mod.encrypt_pii("same-value")
    assert a != b
    assert enc_mod.decrypt_pii(a) == enc_mod.decrypt_pii(b) == "same-value"


def test_encrypt_is_idempotent_on_already_encrypted():
    once = enc_mod.encrypt_pii("secret")
    twice = enc_mod.encrypt_pii(once)
    assert once == twice
    assert enc_mod.decrypt_pii(twice) == "secret"


def test_decrypt_legacy_plaintext_passes_through():
    # A row written before the feature rolled out has no prefix and must
    # be returned unchanged so the rollout is zero-downtime.
    assert enc_mod.decrypt_pii("legacy-plaintext-value") == "legacy-plaintext-value"


def test_encrypt_without_key_passes_through(monkeypatch: pytest.MonkeyPatch):
    from app.config import settings as _settings
    monkeypatch.setattr(_settings, "PII_ENCRYPTION_KEY", "", raising=False)
    enc_mod._reset_cache_for_tests()
    # No key → module is a no-op.
    assert enc_mod.encrypt_pii("hello") == "hello"
    assert enc_mod.decrypt_pii("hello") == "hello"


def test_decrypt_prefixed_without_key_raises(monkeypatch: pytest.MonkeyPatch):
    ct = enc_mod.encrypt_pii("will-be-unreadable")
    # Now remove the key — the data is already encrypted in storage but
    # the key is gone. This must surface loudly, not silently return the
    # ciphertext as if it were plaintext.
    from app.config import settings as _settings
    monkeypatch.setattr(_settings, "PII_ENCRYPTION_KEY", "", raising=False)
    enc_mod._reset_cache_for_tests()
    with pytest.raises(RuntimeError, match="PII_ENCRYPTION_KEY missing"):
        enc_mod.decrypt_pii(ct)


def test_invalid_key_format_treated_as_disabled(monkeypatch: pytest.MonkeyPatch):
    from app.config import settings as _settings
    monkeypatch.setattr(_settings, "PII_ENCRYPTION_KEY", "this-is-not-a-fernet-key", raising=False)
    enc_mod._reset_cache_for_tests()
    # The module logs an error and falls back to no-op rather than 500-ing
    # on startup — a misconfigured key should not bring the API down.
    assert enc_mod.encrypt_pii("x") == "x"


def test_key_rotation_reads_old_ciphertext(monkeypatch: pytest.MonkeyPatch):
    # Encrypt a value under KEY_A, then rotate: new primary = KEY_B,
    # previous = KEY_A. The old ciphertext must still decrypt.
    ct_old = enc_mod.encrypt_pii("rotation-test")
    assert ct_old is not None

    from app.config import settings as _settings
    monkeypatch.setattr(_settings, "PII_ENCRYPTION_KEY", KEY_B, raising=False)
    monkeypatch.setattr(_settings, "PII_ENCRYPTION_KEY_PREVIOUS", KEY_A, raising=False)
    enc_mod._reset_cache_for_tests()

    # Old ciphertext decrypts via the previous-key slot of MultiFernet.
    assert enc_mod.decrypt_pii(ct_old) == "rotation-test"
    # New writes use the new key.
    ct_new = enc_mod.encrypt_pii("rotation-test")
    assert ct_new is not None and ct_new != ct_old
    assert enc_mod.decrypt_pii(ct_new) == "rotation-test"


def test_key_rotation_drops_old_key_makes_old_ct_unreadable(monkeypatch: pytest.MonkeyPatch):
    ct_old = enc_mod.encrypt_pii("will-be-lost")

    from app.config import settings as _settings
    monkeypatch.setattr(_settings, "PII_ENCRYPTION_KEY", KEY_B, raising=False)
    monkeypatch.setattr(_settings, "PII_ENCRYPTION_KEY_PREVIOUS", "", raising=False)
    enc_mod._reset_cache_for_tests()

    # Without the previous key slot, the old ciphertext cannot decrypt
    # and must raise (not silently return garbage).
    with pytest.raises(RuntimeError):
        enc_mod.decrypt_pii(ct_old)


# ── TypeDecorator tests (drive the SQLAlchemy hook points directly) ─────

def test_type_decorator_bind_encrypts():
    col = enc_mod.EncryptedString(512)
    bound = col.process_bind_param("bank-account-1234", dialect=None)
    assert bound is not None
    assert bound.startswith("penc:v1:")


def test_type_decorator_result_decrypts():
    col = enc_mod.EncryptedString(512)
    ct = enc_mod.encrypt_pii("IBAN-SE0000")
    out = col.process_result_value(ct, dialect=None)
    assert out == "IBAN-SE0000"


def test_type_decorator_none_bind_and_result():
    col = enc_mod.EncryptedString(512)
    assert col.process_bind_param(None, dialect=None) is None
    assert col.process_result_value(None, dialect=None) is None


def test_type_decorator_legacy_plaintext_result_passes_through():
    col = enc_mod.EncryptedString(512)
    # Row written before the feature rolled out.
    assert col.process_result_value("legacy-value", dialect=None) == "legacy-value"


def test_type_decorator_roundtrip_simulation():
    # End-to-end: value goes through bind → "storage" → result.
    col = enc_mod.EncryptedString(512)
    stored = col.process_bind_param("round@trip.dev", dialect=None)
    loaded = col.process_result_value(stored, dialect=None)
    assert loaded == "round@trip.dev"
