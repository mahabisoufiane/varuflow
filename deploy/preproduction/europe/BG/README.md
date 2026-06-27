# Bulgaria — preproduction

| Field | Value |
|-------|-------|
| ISO   | BG |
| Region | europe |
| Currency | BGN |
| VAT | 20.0% |
| Locale | bg-BG |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-preproduction-bg)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://bg.varuflow.app
FRONTEND_URL=https://bg.varuflow.app
PORTAL_BASE_URL=https://bg.varuflow.app
DATABASE_URL=<tier-specific Postgres for BG>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-preproduction-bg)
NEXT_PUBLIC_API_URL=https://api-bg-preproduction.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=BG
NEXT_PUBLIC_DEFAULT_LOCALE=bg-BG
NEXT_PUBLIC_DEFAULT_CURRENCY=BGN
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
