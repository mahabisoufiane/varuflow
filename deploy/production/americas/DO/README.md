# Dominican Rep. — production

| Field | Value |
|-------|-------|
| ISO   | DO |
| Region | americas |
| Currency | DOP |
| VAT | 18.0% |
| Locale | es-DO |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-production-do)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://do.varuflow.app
FRONTEND_URL=https://do.varuflow.app
PORTAL_BASE_URL=https://do.varuflow.app
DATABASE_URL=<tier-specific Postgres for DO>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-production-do)
NEXT_PUBLIC_API_URL=https://api-do-production.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=DO
NEXT_PUBLIC_DEFAULT_LOCALE=es-DO
NEXT_PUBLIC_DEFAULT_CURRENCY=DOP
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
