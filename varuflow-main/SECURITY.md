# Security Policy

## Supported versions
Only the latest `main` branch is supported. Past tagged releases do not
receive security patches.

## Reporting a vulnerability
**Do not open a public GitHub issue.**
Email `security@varuflow.se` with:
- A description of the vulnerability
- Steps to reproduce
- The commit hash / environment affected

You should receive an acknowledgement within 72 hours and a fix ETA within
7 business days for critical issues.

## Known accepted risks (with expiration dates)

| ID | Description | Mitigation | Expires |
|----|-------------|------------|---------|
| R-01 | _Resolved_ — `ENFORCE_JWT_SIGNATURE` now defaults to `True`. Production verifies all Supabase JWTs. | n/a | — |
| R-02 | _Resolved_ — `ENFORCE_SECRET_VALIDATION` now defaults to `True`. Startup crashes on placeholder secrets when `ENV != development`. | n/a | — |
| R-03 | Dev auth bypass guarded by `ALLOW_DEV_BYPASS` (default `False`) in addition to `ENV=development`. Both must be set for the unauthenticated dev user to resolve. | Never set `ALLOW_DEV_BYPASS=True` on Railway. | — |

Hardened defaults landed 2026-04-21. A local `.env` must explicitly opt
out (`ENFORCE_JWT_SIGNATURE=false`, `ALLOW_DEV_BYPASS=true`) to run without
a Supabase project. Production (Railway) must never set any of these
overrides.

## Responsible disclosure timeline
- Day 0: report received
- Day 3: acknowledgement + severity assessment
- Day 30: patch released (critical / high)
- Day 90: coordinated public disclosure

## Admin key rotation

The `X-Admin-Key` header authenticates admin-only endpoints (waitlist
export, etc.). The secret is supplied via two environment variables on
Railway so rotation is zero-downtime:

| Env var | Role |
|---------|------|
| `ADMIN_API_KEY`          | Current key. Required. |
| `ADMIN_API_KEY_PREVIOUS` | Optional. Accepted during a rotation window. |

**Runbook**

1. Generate the new secret:
   `python -c "import secrets; print(secrets.token_hex(32))"`.
2. On Railway, set `ADMIN_API_KEY_PREVIOUS` to the CURRENT value of
   `ADMIN_API_KEY`, then set `ADMIN_API_KEY` to the new secret. Deploy.
   Every request made with the old key will now be audit-logged as
   `ADMIN_KEY_ROTATION_USED`.
3. Distribute the new key to operators and any scheduled jobs. Watch
   the audit log until `ADMIN_KEY_ROTATION_USED` entries stop appearing.
4. Clear `ADMIN_API_KEY_PREVIOUS` (set to empty string) and redeploy.
   From this point the old key is rejected.

Rotate at least every 90 days, and immediately after any incident that
might have leaked the key (laptop loss, CI log exposure, ex-employee
offboarding).
