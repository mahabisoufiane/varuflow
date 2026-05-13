#!/usr/bin/env python3
"""check_locales.py — enforce locale completeness in CI.

Compares every ``frontend/messages/<locale>.json`` against
``frontend/messages/en.json`` (the source-of-truth) and exits non-zero
when a locale is missing keys or has extra/unknown keys. Shape
(nested object vs leaf string) must also match.

Run from repo root:
    python3 scripts/check_locales.py          # verify only (CI)
    python3 scripts/check_locales.py --sync   # backfill missing keys
                                              # with English values

Env knobs:
    LOCALES_IGNORE=sq,mk                skip specific locales (comma-sep).

Exit codes:
    0 — every locale matches en.json key-for-key
    1 — at least one locale has missing or extra keys, or a type mismatch
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MSGS = ROOT / "frontend" / "messages"
BASE_LOCALE = "en"
# Locale files that are not real UI bundles and should be skipped.
SKIP_FILES = {"_archived"}
# Top-level namespaces that are purely locale metadata (direction, code,
# script, …) and deliberately vary across files. Ignored by the drift
# checker so a locale can self-describe without breaking CI.
IGNORED_TOP_LEVEL_KEYS = {"_meta"}


def _flatten(obj: dict, prefix: str = "") -> dict[str, str]:
    """Recursively flatten a nested message dict into dotted keys.

    The resulting dict's values are the runtime string type each path
    resolves to: ``"str"`` for leaves, ``"obj"`` for nested namespaces.
    We need both so that reshaping a leaf into a nested namespace (or
    vice-versa) is flagged as a structural drift, not a silent rename.
    """
    out: dict[str, str] = {}
    for k, v in obj.items():
        path = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out[path] = "obj"
            out.update(_flatten(v, path))
        else:
            out[path] = "str"
    return out


def _load(locale: str) -> dict:
    with open(MSGS / f"{locale}.json", encoding="utf-8") as f:
        return json.load(f)


def _dump(locale: str, data: dict) -> None:
    with open(MSGS / f"{locale}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _merge_missing(base: dict, peer: dict) -> tuple[dict, int]:
    """Return (merged, added_count). English values fill gaps, existing
    peer translations are preserved untouched."""
    added = 0
    out: dict = {}
    for k, v in base.items():
        if isinstance(v, dict):
            peer_sub = peer.get(k) if isinstance(peer.get(k), dict) else {}
            merged_sub, sub_added = _merge_missing(v, peer_sub)
            out[k] = merged_sub
            added += sub_added
        else:
            if k in peer and not isinstance(peer[k], dict):
                out[k] = peer[k]
            else:
                out[k] = v
                added += 1
    return out, added


def main() -> int:
    sync = "--sync" in sys.argv[1:]
    if not (MSGS / f"{BASE_LOCALE}.json").exists():
        print(f"error: base locale {BASE_LOCALE}.json missing", file=sys.stderr)
        return 1

    ignore = {
        c.strip()
        for c in os.environ.get("LOCALES_IGNORE", "").split(",")
        if c.strip()
    }

    base_raw = _load(BASE_LOCALE)
    base = _flatten(base_raw)

    locales = sorted(
        p.stem for p in MSGS.glob("*.json")
        if p.stem != BASE_LOCALE and p.stem not in SKIP_FILES
    )

    failed = False
    for locale in locales:
        if locale in ignore:
            continue
        try:
            peer_raw = _load(locale)
        except json.JSONDecodeError as e:
            print(f"[{locale}] JSON parse error: {e}", file=sys.stderr)
            failed = True
            continue

        if sync:
            merged, added = _merge_missing(base_raw, peer_raw)
            if added:
                _dump(locale, merged)
                print(f"[{locale}] synced {added} missing key(s) from {BASE_LOCALE}")
            peer_raw = merged

        peer = _flatten(peer_raw)

        def _filtered(keys):
            return [
                k for k in keys
                if k.split(".", 1)[0] not in IGNORED_TOP_LEVEL_KEYS
            ]

        missing = sorted(_filtered(k for k in base if k not in peer))
        extra = sorted(_filtered(k for k in peer if k not in base))
        mismatched = sorted(_filtered(
            k for k in base
            if k in peer and base[k] != peer[k]
        ))

        if missing or extra or mismatched:
            failed = True
            print(f"[{locale}] drift vs {BASE_LOCALE}.json:", file=sys.stderr)
            for k in missing[:50]:
                print(f"  - missing: {k}", file=sys.stderr)
            if len(missing) > 50:
                print(f"  … +{len(missing) - 50} more missing", file=sys.stderr)
            for k in extra[:50]:
                print(f"  + extra:   {k}", file=sys.stderr)
            if len(extra) > 50:
                print(f"  … +{len(extra) - 50} more extra", file=sys.stderr)
            for k in mismatched[:20]:
                print(
                    f"  ~ shape:   {k} "
                    f"({base[k]} in {BASE_LOCALE}, {peer[k]} in {locale})",
                    file=sys.stderr,
                )

    if failed:
        print(
            "\nlocales check FAILED — run "
            "`python3 scripts/check_locales.py --sync` to backfill "
            "missing keys with English fallbacks, then hand-translate.",
            file=sys.stderr,
        )
        return 1

    print(f"locales check OK — {len(locales)} locales aligned with {BASE_LOCALE}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
