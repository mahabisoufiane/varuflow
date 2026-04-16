# Lithuania — production

| Field | Value |
|-------|-------|
| ISO   | LT |
| Region | europe |
| Currency | EUR |
| VAT | 21.0% |
| Locale | lt-LT |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-production-lt)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://lt.varuflow.app
FRONTEND_URL=https://lt.varuflow.app
PORTAL_BASE_URL=https://lt.varuflow.app
DATABASE_URL=<tier-specific Postgres for LT>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-production-lt)
NEXT_PUBLIC_API_URL=https://api-lt-production.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=LT
NEXT_PUBLIC_DEFAULT_LOCALE=lt-LT
NEXT_PUBLIC_DEFAULT_CURRENCY=EUR
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
