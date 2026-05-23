"""Pure helpers for saved filters (Item 61).

The saved filter's ``definition`` is a structured dict; we validate
it here so the router stays thin and the rules are unit-testable.

Accepted shape
--------------
```json
{
    "clauses": [
        {"field": "status", "op": "eq", "value": "OVERDUE"},
        {"field": "total", "op": "gte", "value": 1000}
    ],
    "sort": [{"field": "issue_date", "dir": "desc"}]
}
```

Supported ops: ``eq``, ``neq``, ``gt``, ``gte``, ``lt``, ``lte``,
``in``, ``contains``, ``between``. Field names are whitespace-free
and length-capped. Clause values are strings / numbers / booleans /
list-of-strings-for-in.

The service doesn't execute the filter — that's the list router's
job — so we can't know which fields are legal on a given entity.
We keep the structural check strict (unknown keys rejected, nested
dicts rejected) so anything that parses here is a well-formed query.
"""
from __future__ import annotations

import re
from typing import Any

ALLOWED_ENTITY_TYPES: frozenset[str] = frozenset({
    "product", "customer", "invoice", "appointment",
})
ALLOWED_OPS: frozenset[str] = frozenset({
    "eq", "neq", "gt", "gte", "lt", "lte",
    "in", "contains", "between",
})
ALLOWED_SORT_DIRS: frozenset[str] = frozenset({"asc", "desc"})

MAX_NAME_LENGTH: int = 120
MAX_FIELD_LENGTH: int = 64
MAX_CLAUSES: int = 20
MAX_SORT_COLUMNS: int = 4
MAX_IN_VALUES: int = 100
MAX_TEXT_VALUE_LENGTH: int = 255

_FIELD_RE = re.compile(r"^[a-z][a-z0-9_.]{0,63}$")


def _validate_field(field: Any) -> None:
    if not isinstance(field, str) or not _FIELD_RE.match(field):
        raise ValueError(
            "clause.field must be lowercase snake_case, "
            f"1..{MAX_FIELD_LENGTH} chars"
        )


def _validate_scalar(v: Any) -> None:
    if isinstance(v, bool):
        return
    if isinstance(v, (int, float)):
        return
    if isinstance(v, str):
        if len(v) > MAX_TEXT_VALUE_LENGTH:
            raise ValueError(
                f"text value exceeds {MAX_TEXT_VALUE_LENGTH} chars"
            )
        return
    raise ValueError("value must be str, number or boolean")


def _validate_clause(clause: Any) -> None:
    if not isinstance(clause, dict):
        raise ValueError("clause must be an object")
    unknown = set(clause.keys()) - {"field", "op", "value"}
    if unknown:
        raise ValueError(f"unknown clause keys: {sorted(unknown)}")
    _validate_field(clause.get("field"))
    op = clause.get("op")
    if op not in ALLOWED_OPS:
        raise ValueError(f"op must be one of {sorted(ALLOWED_OPS)}")

    value = clause.get("value")
    if op == "in":
        if not isinstance(value, list) or not value:
            raise ValueError("'in' value must be a non-empty list")
        if len(value) > MAX_IN_VALUES:
            raise ValueError(f"'in' list too long ({MAX_IN_VALUES} max)")
        for item in value:
            _validate_scalar(item)
    elif op == "between":
        if (
            not isinstance(value, list)
            or len(value) != 2
        ):
            raise ValueError("'between' value must be a 2-element list")
        for item in value:
            _validate_scalar(item)
    else:
        _validate_scalar(value)


def _validate_sort(sort: Any) -> None:
    if sort is None:
        return
    if not isinstance(sort, list):
        raise ValueError("sort must be a list")
    if len(sort) > MAX_SORT_COLUMNS:
        raise ValueError(f"sort supports up to {MAX_SORT_COLUMNS} columns")
    for row in sort:
        if not isinstance(row, dict):
            raise ValueError("sort row must be an object")
        unknown = set(row.keys()) - {"field", "dir"}
        if unknown:
            raise ValueError(f"unknown sort keys: {sorted(unknown)}")
        _validate_field(row.get("field"))
        if row.get("dir") not in ALLOWED_SORT_DIRS:
            raise ValueError(
                f"sort.dir must be one of {sorted(ALLOWED_SORT_DIRS)}"
            )


def validate_definition(definition: Any) -> dict:
    """Validate ``definition`` and return the canonical dict.

    Raises :class:`ValueError` with a human-readable message on any
    shape violation.
    """
    if not isinstance(definition, dict):
        raise ValueError("definition must be an object")
    unknown = set(definition.keys()) - {"clauses", "sort"}
    if unknown:
        raise ValueError(f"unknown top-level keys: {sorted(unknown)}")

    clauses = definition.get("clauses", [])
    if not isinstance(clauses, list):
        raise ValueError("clauses must be a list")
    if len(clauses) > MAX_CLAUSES:
        raise ValueError(f"too many clauses ({MAX_CLAUSES} max)")
    for c in clauses:
        _validate_clause(c)

    _validate_sort(definition.get("sort"))

    # Return a normalised shape: "sort" always present (possibly empty
    # list) so consumers don't need to branch.
    return {
        "clauses": clauses,
        "sort": definition.get("sort") or [],
    }


def validate_name(name: str | None) -> str:
    if not name:
        raise ValueError("name is required")
    s = " ".join(name.strip().split())
    if not s:
        raise ValueError("name is required")
    if len(s) > MAX_NAME_LENGTH:
        raise ValueError(f"name too long ({MAX_NAME_LENGTH} chars max)")
    return s


def validate_entity_type(entity_type: str) -> None:
    if entity_type not in ALLOWED_ENTITY_TYPES:
        raise ValueError(
            f"entity_type must be one of {sorted(ALLOWED_ENTITY_TYPES)}"
        )


def can_edit(filter_user_id, requester_user_id, requester_is_owner: bool) -> bool:
    """Edit rules: the row's owner, or an org OWNER for shared rows."""
    if str(filter_user_id) == str(requester_user_id):
        return True
    if requester_is_owner:
        return True
    return False
