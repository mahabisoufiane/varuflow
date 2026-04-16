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
| R-01 | JWT signature verification opt-in via `ENFORCE_JWT_SIGNATURE` env flag | Flag must be set to `True` in Railway before public launch | before GA |
| R-02 | Placeholder secret validator opt-in via `ENFORCE_SECRET_VALIDATION` | Flag must be set to `True` in Railway before public launch | before GA |

Both flags default to `False` to keep the current Railway deployment
working while the Supabase JWT secret is being confirmed. The gated code
paths are implemented and verified — only the env flags need to be
flipped once the secret rotation is complete.

## Responsible disclosure timeline
- Day 0: report received
- Day 3: acknowledgement + severity assessment
- Day 30: patch released (critical / high)
- Day 90: coordinated public disclosure
