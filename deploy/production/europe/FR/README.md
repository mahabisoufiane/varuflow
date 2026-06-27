# France — production

| Field | Value |
|-------|-------|
| ISO   | FR |
| Region | europe |
| Currency | EUR |
| VAT | 20.0% |
| Locale | fr-FR |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-production-fr)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://fr.varuflow.app
FRONTEND_URL=https://fr.varuflow.app
PORTAL_BASE_URL=https://fr.varuflow.app
DATABASE_URL=<tier-specific Postgres for FR>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-production-fr)
NEXT_PUBLIC_API_URL=https://api-fr-production.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=FR
NEXT_PUBLIC_DEFAULT_LOCALE=fr-FR
NEXT_PUBLIC_DEFAULT_CURRENCY=EUR
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
