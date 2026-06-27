"""MFA enforcement rules for owner accounts (Item 23).

Pure functions — no DB access, no I/O — so they can be unit-tested with
plain values and reused by both the runtime gate
(``middleware/auth.require_mfa_if_enforced``) and the status endpoint
(``routers/settings_security``).

Rule
----
An owner account MUST have TOTP enabled on sensitive routes
(team mutations, billing checkout/portal) when any of the following is
true:

* The org is on the PRO plan.
* The org is on the ENTERPRISE plan.
* The org has at least ``MFA_MEMBER_THRESHOLD`` members (regardless of
  plan — a free-tier team large enough to matter to a small business
  also has enough attack surface to warrant MFA).

Non-owners are never enforced here (ADMIN/MEMBER accounts inherit trust
from the owner's hardening posture; we can add per-role enforcement in
a future item without breaking the owner-only API below).
"""
from __future__ import annotations

from app.features.auth.organization import OrgPlan

# A FREE org with five or more members is treated as "enough people to
# care about" — an attacker phishing the owner of such a team can exfil
# multi-user data, not just a solo's records. Keeping the threshold as a
# named constant so we can tune it from one place (and so the tests can
# import it rather than hard-coding the number).
MFA_MEMBER_THRESHOLD = 5


def is_mfa_required_for_owner(plan: OrgPlan, member_count: int) -> bool:
    """Return True iff the owner of this org must have TOTP enabled.

    See module docstring for the rule. Callers supply ``member_count``
    already scoped to the org — this function deliberately does not
    touch the database so it's trivially testable.
    """
    if plan in (OrgPlan.PRO, OrgPlan.ENTERPRISE):
        return True
    return member_count >= MFA_MEMBER_THRESHOLD
