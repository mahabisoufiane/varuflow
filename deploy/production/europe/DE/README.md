# Germany — production

| Field | Value |
|-------|-------|
| ISO   | DE |
| Region | europe |
| Currency | EUR |
| VAT | 19.0% |
| Locale | de-DE |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-production-de)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://de.varuflow.app
FRONTEND_URL=https://de.varuflow.app
PORTAL_BASE_URL=https://de.varuflow.app
DATABASE_URL=<tier-specific Postgres for DE>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-production-de)
NEXT_PUBLIC_API_URL=https://api-de-production.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=DE
NEXT_PUBLIC_DEFAULT_LOCALE=de-DE
NEXT_PUBLIC_DEFAULT_CURRENCY=EUR
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
