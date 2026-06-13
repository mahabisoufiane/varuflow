"""IP allowlist matching + CIDR validation (Item 25).

Pure helpers — no DB, no I/O — so both the runtime gate
(``middleware/auth.get_current_member``) and the CRUD router
(``routers/settings_security``) share one validator and one matcher
with the test suite.
"""
from __future__ import annotations

import ipaddress


def parse_cidr(raw: str) -> str:
    """Validate and normalise a CIDR / bare IP string.

    * ``"203.0.113.5"``       → ``"203.0.113.5/32"``
    * ``"203.0.113.0/24"``    → ``"203.0.113.0/24"``
    * ``"2001:db8::/32"``     → ``"2001:db8::/32"``

    Raises :class:`ValueError` on anything else (empty string, garbage,
    host-bits-set CIDR like ``203.0.113.5/24`` — we set ``strict=True``
    so a sloppy allowlist entry doesn't silently mean something other
    than the user typed).
    """
    if not raw or not isinstance(raw, str):
        raise ValueError("CIDR must be a non-empty string")
    text = raw.strip()
    if not text:
        raise ValueError("CIDR must be a non-empty string")
    # ``ip_network`` accepts both "5.5.5.5" (→ /32) and "5.5.5.0/24".
    # strict=True rejects "5.5.5.5/24" (host bits set) — that's almost
    # always a typo on a firewall allowlist.
    network = ipaddress.ip_network(text, strict=True)
    return str(network)


def ip_matches_allowlist(client_ip: str | None, cidrs: list[str]) -> bool:
    """Return True iff ``client_ip`` falls inside any of ``cidrs``.

    * Empty ``cidrs`` → False (caller is expected to interpret that as
      "allowlist not configured; allow-by-default" — this helper stays
      strict so an empty list can never accidentally mean "allow all").
    * Unparseable ``client_ip`` → False. An attacker setting a bogus
      ``X-Forwarded-For`` header shouldn't be able to bypass by sending
      a non-IP value.
    * Unparseable entries in ``cidrs`` are skipped (stale DB rows from
      a future schema change shouldn't 500 the request).
    """
    if not cidrs:
        return False
    if not client_ip:
        return False
    try:
        ip = ipaddress.ip_address(client_ip)
    except (ValueError, TypeError):
        return False
    for raw in cidrs:
        try:
            if ip in ipaddress.ip_network(raw, strict=False):
                return True
        except (ValueError, TypeError):
            continue
    return False
