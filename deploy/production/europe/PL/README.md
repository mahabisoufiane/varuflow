# Poland — production

| Field | Value |
|-------|-------|
| ISO   | PL |
| Region | europe |
| Currency | PLN |
| VAT | 23.0% |
| Locale | pl-PL |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-production-pl)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://pl.varuflow.app
FRONTEND_URL=https://pl.varuflow.app
PORTAL_BASE_URL=https://pl.varuflow.app
DATABASE_URL=<tier-specific Postgres for PL>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-production-pl)
NEXT_PUBLIC_API_URL=https://api-pl-production.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=PL
NEXT_PUBLIC_DEFAULT_LOCALE=pl-PL
NEXT_PUBLIC_DEFAULT_CURRENCY=PLN
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
