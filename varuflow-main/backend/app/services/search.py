"""Smart Search — Global (Item 55).

Pure helpers for the global search endpoint. The router is thin: it
pulls candidate rows from each entity table using an ILIKE predicate
scoped to the caller's org, then hands them here for scoring and
ranking.

The scoring model is intentionally simple and deterministic so that
behaviour is testable without a database:

* **Exact (case-insensitive) match** on the primary identifier →
  ``100``.
* **Prefix match** on any searchable field → ``60``.
* **Substring match** on any searchable field → ``30``.
* No match → ``0`` (excluded from results).

Entity type ordering when scores tie (customers first because the
usual intent of a cross-entity search is "find this company") is:

    ``customer > invoice > product > staff``

The router caps results per entity at ``MAX_PER_ENTITY`` so a single
prolific entity type cannot starve the others.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

# Hard caps — the router must enforce both.
MAX_PER_ENTITY: int = 5
MAX_QUERY_LENGTH: int = 100
MIN_QUERY_LENGTH: int = 2

# Score constants. Public so tests can reference them instead of
# hard-coding numbers.
SCORE_EXACT: int = 100
SCORE_PREFIX: int = 60
SCORE_SUBSTRING: int = 30
SCORE_NONE: int = 0

# Stable tie-break order. Lower index = higher priority on tie.
ENTITY_PRIORITY: tuple[str, ...] = ("customer", "invoice", "product", "staff")


@dataclass(frozen=True)
class SearchHit:
    """One row returned by the search endpoint."""
    entity_type: str         # "customer" | "invoice" | "product" | "staff"
    entity_id:   str         # stringified UUID
    title:       str         # what to show as the primary label
    subtitle:    str | None  # secondary identifier (sku, org_nr, etc.)
    score:       int         # see ``score_field``


def normalise_query(raw: str | None) -> str:
    """Trim + collapse whitespace + lowercase.

    Returns an empty string when ``raw`` is ``None``, blank or shorter
    than :data:`MIN_QUERY_LENGTH`. The router should treat the empty
    string as "reject with 400".
    """
    if raw is None:
        return ""
    q = " ".join(raw.strip().split()).lower()
    if len(q) < MIN_QUERY_LENGTH:
        return ""
    if len(q) > MAX_QUERY_LENGTH:
        q = q[:MAX_QUERY_LENGTH]
    return q


def escape_like(q: str) -> str:
    """Escape SQL LIKE wildcards in the user query.

    Postgres' ILIKE treats ``%`` and ``_`` as wildcards. Without
    escaping, a user typing ``100%`` would match everything. The
    backslash is doubled so the escape char survives the parameter
    substitution.
    """
    return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def score_field(query: str, candidate: str | None) -> int:
    """Score one candidate string against a *normalised* query.

    ``query`` MUST already have been through :func:`normalise_query`.
    """
    if not candidate or not query:
        return SCORE_NONE
    c = candidate.lower()
    if c == query:
        return SCORE_EXACT
    if c.startswith(query):
        return SCORE_PREFIX
    if query in c:
        return SCORE_SUBSTRING
    return SCORE_NONE


def best_score(query: str, candidates: Iterable[str | None]) -> int:
    """Highest :func:`score_field` across multiple candidate strings."""
    best = SCORE_NONE
    for c in candidates:
        s = score_field(query, c)
        if s > best:
            best = s
            if best == SCORE_EXACT:
                break
    return best


def rank_hits(hits: Iterable[SearchHit]) -> list[SearchHit]:
    """Sort hits by score desc, then by entity priority, then title."""
    priority = {name: i for i, name in enumerate(ENTITY_PRIORITY)}

    def _key(h: SearchHit) -> tuple[int, int, str]:
        return (-h.score, priority.get(h.entity_type, len(priority)), h.title.lower())

    return sorted(hits, key=_key)


def group_by_entity(hits: Iterable[SearchHit]) -> dict[str, list[SearchHit]]:
    """Split a ranked list into per-entity buckets, preserving order."""
    out: dict[str, list[SearchHit]] = {name: [] for name in ENTITY_PRIORITY}
    for h in hits:
        out.setdefault(h.entity_type, []).append(h)
    return out
