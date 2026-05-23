"""Unit tests for scripts/check_locales.py (Feature 11).

We build an ephemeral `frontend/messages/` tree in a tmp dir, point
the script at it via monkey-patching its module-level ``MSGS`` path,
and assert on the returned exit code + side-effects.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_locales.py"


def _load_script(tmp_msgs: Path):
    """Load scripts/check_locales.py as a module and redirect its MSGS
    root to the tmp test fixture."""
    spec = importlib.util.spec_from_file_location("check_locales", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.MSGS = tmp_msgs
    return mod


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def test_passes_when_locales_match(tmp_path, monkeypatch):
    msgs = tmp_path / "messages"
    msgs.mkdir()
    _write(msgs / "en.json", {"nav": {"home": "Home"}, "hello": "Hi"})
    _write(msgs / "sv.json", {"nav": {"home": "Hem"}, "hello": "Hej"})

    mod = _load_script(msgs)
    monkeypatch.setattr(sys, "argv", ["check_locales.py"])
    assert mod.main() == 0


def test_fails_on_missing_key(tmp_path, monkeypatch):
    msgs = tmp_path / "messages"
    msgs.mkdir()
    _write(msgs / "en.json", {"hello": "Hi", "bye": "Bye"})
    _write(msgs / "fr.json", {"hello": "Salut"})  # missing "bye"

    mod = _load_script(msgs)
    monkeypatch.setattr(sys, "argv", ["check_locales.py"])
    assert mod.main() == 1


def test_fails_on_extra_key(tmp_path, monkeypatch):
    msgs = tmp_path / "messages"
    msgs.mkdir()
    _write(msgs / "en.json", {"hello": "Hi"})
    _write(msgs / "de.json", {"hello": "Hallo", "ghost": "x"})

    mod = _load_script(msgs)
    monkeypatch.setattr(sys, "argv", ["check_locales.py"])
    assert mod.main() == 1


def test_fails_on_shape_mismatch(tmp_path, monkeypatch):
    """Key at same path must be a leaf in both or an object in both."""
    msgs = tmp_path / "messages"
    msgs.mkdir()
    _write(msgs / "en.json", {"nav": {"home": "Home"}})
    _write(msgs / "it.json", {"nav": "Navigation"})  # leaf, should be obj

    mod = _load_script(msgs)
    monkeypatch.setattr(sys, "argv", ["check_locales.py"])
    assert mod.main() == 1


def test_sync_backfills_missing_keys(tmp_path, monkeypatch):
    msgs = tmp_path / "messages"
    msgs.mkdir()
    _write(msgs / "en.json", {"a": "A", "b": {"c": "C"}})
    _write(msgs / "pl.json", {"a": "A-pl"})  # missing b.c

    mod = _load_script(msgs)
    monkeypatch.setattr(sys, "argv", ["check_locales.py", "--sync"])
    rc = mod.main()
    # Returns 0 because after --sync the files are aligned.
    assert rc == 0

    pl = json.loads((msgs / "pl.json").read_text(encoding="utf-8"))
    assert pl["a"] == "A-pl"  # existing translation preserved
    assert pl["b"]["c"] == "C"  # missing key filled from en


def test_meta_namespace_is_ignored(tmp_path, monkeypatch):
    """_meta is deliberately excluded from drift checks."""
    msgs = tmp_path / "messages"
    msgs.mkdir()
    _write(msgs / "en.json", {"hello": "Hi"})
    _write(msgs / "ar.json", {"hello": "مرحبا", "_meta": {"dir": "rtl"}})

    mod = _load_script(msgs)
    monkeypatch.setattr(sys, "argv", ["check_locales.py"])
    assert mod.main() == 0
