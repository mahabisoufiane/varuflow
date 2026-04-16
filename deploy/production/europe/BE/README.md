# Belgium — production

| Field | Value |
|-------|-------|
| ISO   | BE |
| Region | europe |
| Currency | EUR |
| VAT | 21.0% |
| Locale | nl-BE |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-production-be)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://be.varuflow.app
FRONTEND_URL=https://be.varuflow.app
PORTAL_BASE_URL=https://be.varuflow.app
DATABASE_URL=<tier-specific Postgres for BE>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-production-be)
NEXT_PUBLIC_API_URL=https://api-be-production.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=BE
NEXT_PUBLIC_DEFAULT_LOCALE=nl-BE
NEXT_PUBLIC_DEFAULT_CURRENCY=EUR
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
