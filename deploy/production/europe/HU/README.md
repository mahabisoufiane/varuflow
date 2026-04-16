# Hungary — production

| Field | Value |
|-------|-------|
| ISO   | HU |
| Region | europe |
| Currency | HUF |
| VAT | 27.0% |
| Locale | hu-HU |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-production-hu)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://hu.varuflow.app
FRONTEND_URL=https://hu.varuflow.app
PORTAL_BASE_URL=https://hu.varuflow.app
DATABASE_URL=<tier-specific Postgres for HU>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-production-hu)
NEXT_PUBLIC_API_URL=https://api-hu-production.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=HU
NEXT_PUBLIC_DEFAULT_LOCALE=hu-HU
NEXT_PUBLIC_DEFAULT_CURRENCY=HUF
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
