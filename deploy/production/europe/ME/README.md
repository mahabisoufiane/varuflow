# Montenegro — production

| Field | Value |
|-------|-------|
| ISO   | ME |
| Region | europe |
| Currency | EUR |
| VAT | 21.0% |
| Locale | sr-ME |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-production-me)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://me.varuflow.app
FRONTEND_URL=https://me.varuflow.app
PORTAL_BASE_URL=https://me.varuflow.app
DATABASE_URL=<tier-specific Postgres for ME>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-production-me)
NEXT_PUBLIC_API_URL=https://api-me-production.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=ME
NEXT_PUBLIC_DEFAULT_LOCALE=sr-ME
NEXT_PUBLIC_DEFAULT_CURRENCY=EUR
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
