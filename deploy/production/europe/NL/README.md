# Netherlands — production

| Field | Value |
|-------|-------|
| ISO   | NL |
| Region | europe |
| Currency | EUR |
| VAT | 21.0% |
| Locale | nl-NL |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-production-nl)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://nl.varuflow.app
FRONTEND_URL=https://nl.varuflow.app
PORTAL_BASE_URL=https://nl.varuflow.app
DATABASE_URL=<tier-specific Postgres for NL>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-production-nl)
NEXT_PUBLIC_API_URL=https://api-nl-production.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=NL
NEXT_PUBLIC_DEFAULT_LOCALE=nl-NL
NEXT_PUBLIC_DEFAULT_CURRENCY=EUR
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
