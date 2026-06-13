"""Item 55 — Global Smart Search.

Pure + source-contract tests for the ``/api/search`` endpoint. We
don't hit a DB: all scoring, ranking, grouping and normalisation lives
in :mod:`app.services.search` and is unit-testable directly. The
router contract is verified by reading the source and asserting the
structural invariants every reviewer would check by eye.
"""
from __future__ import annotations

import pathlib

from app.services import search as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(relpath: str) -> str:
    return (_BACKEND_ROOT / relpath).read_text()


ROUTER_SRC = _read("app/routers/search.py")
SERVICE_SRC = _read("app/services/search.py")
MAIN_SRC = _read("app/main.py")


# ── 1. Normalisation ──────────────────────────────────────────────────────


def test_normalise_query_trims_and_lowercases():
    assert svc.normalise_query("  AcmeCorp  ") == "acmecorp"
    assert svc.normalise_query("INV 2024") == "inv 2024"


def test_normalise_query_rejects_too_short():
    assert svc.normalise_query("") == ""
    assert svc.normalise_query("a") == ""
    assert svc.normalise_query(None) == ""


def test_normalise_query_caps_length():
    long = "x" * 200
    out = svc.normalise_query(long)
    assert len(out) == svc.MAX_QUERY_LENGTH


# ── 2. Scoring ────────────────────────────────────────────────────────────


def test_score_exact_match():
    assert svc.score_field("acme", "ACME") == svc.SCORE_EXACT


def test_score_prefix_match():
    assert svc.score_field("acm", "AcmeCorp") == svc.SCORE_PREFIX


def test_score_substring_match():
    assert svc.score_field("cor", "AcmeCorp") == svc.SCORE_SUBSTRING


def test_score_no_match_and_empty_candidates():
    assert svc.score_field("zzz", "AcmeCorp") == svc.SCORE_NONE
    assert svc.score_field("acme", None) == svc.SCORE_NONE
    assert svc.score_field("", "AcmeCorp") == svc.SCORE_NONE


def test_best_score_picks_highest():
    assert svc.best_score("acme", ["other", "AcmeCorp", None]) == svc.SCORE_PREFIX
    assert svc.best_score("acme", ["ACME", "AcmeCorp"]) == svc.SCORE_EXACT
    assert svc.best_score("xyz", ["a", "b", None]) == svc.SCORE_NONE


# ── 3. Ranking + grouping ─────────────────────────────────────────────────


def test_rank_orders_by_score_then_priority():
    hits = [
        svc.SearchHit("product", "1", "Acme widget", "SKU1", svc.SCORE_SUBSTRING),
        svc.SearchHit("customer", "2", "Acme AB", "556", svc.SCORE_SUBSTRING),
        svc.SearchHit("invoice", "3", "INV-ACME", None, svc.SCORE_EXACT),
    ]
    ranked = svc.rank_hits(hits)
    # Exact first regardless of entity
    assert ranked[0].entity_type == "invoice"
    # At same score, customer beats product
    assert ranked[1].entity_type == "customer"
    assert ranked[2].entity_type == "product"


def test_group_by_entity_keeps_priority_keys():
    ranked = [
        svc.SearchHit("product", "1", "P", None, svc.SCORE_EXACT),
        svc.SearchHit("customer", "2", "C", None, svc.SCORE_PREFIX),
    ]
    grouped = svc.group_by_entity(ranked)
    assert list(grouped.keys())[:4] == list(svc.ENTITY_PRIORITY)
    assert len(grouped["product"]) == 1
    assert len(grouped["customer"]) == 1
    assert grouped["invoice"] == []
    assert grouped["staff"] == []


# ── 4. LIKE-escape safety (OWASP A03 — injection) ─────────────────────────


def test_escape_like_neutralises_wildcards():
    assert svc.escape_like("100%") == r"100\%"
    assert svc.escape_like("a_b") == r"a\_b"
    # Backslash itself is doubled so it survives parameter binding.
    assert svc.escape_like("a\\b") == r"a\\b"


# ── 5. Router source-contract ─────────────────────────────────────────────


def test_router_registered_on_api_search():
    assert 'prefix="/api/search"' in ROUTER_SRC
    assert "app.include_router(search.router)" in MAIN_SRC


def test_router_is_tenant_scoped():
    # Every query must filter on the caller's org_id — the single most
    # important invariant for a multi-tenant search endpoint.
    assert "member.org_id" in ROUTER_SRC
    assert ROUTER_SRC.count("org_id == org_id") >= 4  # customer + invoice + product + staff


def test_router_rejects_short_query():
    assert "Query must be at least" in ROUTER_SRC
    assert "HTTP_400_BAD_REQUEST" in ROUTER_SRC


def test_router_uses_escape_backslash_on_ilike():
    # Confirms every ILIKE call wires up the backslash escape char —
    # matches the escape our ``escape_like`` helper emits.
    assert ROUTER_SRC.count('escape="\\\\"') >= 4


def test_router_caps_results_per_entity():
    assert "MAX_PER_ENTITY" in ROUTER_SRC
    assert "[:limit]" in ROUTER_SRC


def test_router_supports_types_filter():
    assert "_parse_types" in ROUTER_SRC
    # Unknown types produce a 400, not a silent ignore.
    assert "Unknown entity type" in ROUTER_SRC


def test_router_uses_get_current_member():
    # Any authenticated member may search — not a role-gated endpoint.
    assert "Depends(get_current_member)" in ROUTER_SRC
