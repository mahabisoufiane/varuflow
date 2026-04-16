# Malta — production

| Field | Value |
|-------|-------|
| ISO   | MT |
| Region | europe |
| Currency | EUR |
| VAT | 18.0% |
| Locale | en-MT |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-production-mt)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://mt.varuflow.app
FRONTEND_URL=https://mt.varuflow.app
PORTAL_BASE_URL=https://mt.varuflow.app
DATABASE_URL=<tier-specific Postgres for MT>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-production-mt)
NEXT_PUBLIC_API_URL=https://api-mt-production.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=MT
NEXT_PUBLIC_DEFAULT_LOCALE=en-MT
NEXT_PUBLIC_DEFAULT_CURRENCY=EUR
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
